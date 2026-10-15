import json
from copy import deepcopy
from uuid import uuid4
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.utils import timezone
from wallet.models import Wallet, WalletEntry
from .models import DemoSlip, FeedSnapshot
from .slips import submit


class DemoSlipTests(TestCase):
    def test_my_history_is_member_scoped_and_filters_source(self):
        slip=submit(self.member,self.data)
        self.assertEqual(self.client.get('/api/sports/my-slips/').status_code,401)
        self.client.force_login(self.member)
        response=self.client.get('/api/sports/my-slips/')
        self.assertEqual([item['id'] for item in response.json()['items']],[slip.pk])
        self.assertEqual(self.client.get('/api/sports/my-slips/?source=powerball').json()['items'],[])
        self.assertEqual(self.client.get('/api/sports/my-slips/?source=invalid').status_code,400)
        self.assertEqual(self.client.post('/api/sports/my-slips/').status_code,405)
        other=get_user_model().objects.create_user(username='history_other')
        self.client.force_login(other)
        self.assertEqual(self.client.get('/api/sports/my-slips/').json()['items'],[])

    def setUp(self):
        self.member = get_user_model().objects.create_user(username='demo_member')
        self.wallet = Wallet.objects.create(member=self.member, available=100000)
        self.events = []
        for i, odd in enumerate(['2.0000', '3.0000']):
            self.events.append({'id': f'e{i}', 'home': f'Home{i}', 'away': f'Away{i}', 'league': 'Test',
                'startsAt': (timezone.now() + timedelta(days=2)).isoformat(), 'status': 'scheduled', 'completed': False,
                'bookmakers': [{'key': 'test', 'title': 'Test', 'markets': [{'key': 'h2h',
                    'outcomes': [{'name': f'Home{i}', 'price': odd, 'point': None, 'description': ''}]}]}]})
        self.snapshot = FeedSnapshot.objects.create(pk=1, payload={'items': self.events})
        self.data = {'requestId': str(uuid4()), 'mode': 'multi', 'stake': '10000', 'picks': [
            {'eventId': e['id'], 'bookKey': 'test', 'market': 'h2h', **e['bookmakers'][0]['markets'][0]['outcomes'][0]}
            for e in self.events]}

    def balance(self):
        self.wallet.refresh_from_db()
        return self.wallet.available

    def test_multi_uses_server_odds_and_deducts_once(self):
        slip = submit(self.member, self.data)
        self.assertEqual((slip.total_stake, slip.expected_return), (10000, 60000))
        self.assertEqual(submit(self.member, self.data).pk, slip.pk)
        self.assertEqual(self.balance(), 90000)
        self.assertEqual(WalletEntry.objects.get().available_delta, -10000)
        self.assertEqual(DemoSlip.objects.count(), 1)

    def test_manual_price_is_enforced_and_saved_slip_unchanged(self):
        from catalog.models import ManualOdds
        from catalog.odds import choices
        slip = submit(self.member, self.data)
        key = next(choices(self.events[0], 'sports'))[0]
        ManualOdds.objects.create(source='sports', event_id='e0', prices={key:'2.5000'}, updated_by=self.member)
        self.data['requestId'] = str(uuid4())
        with self.assertRaises(ValidationError):
            submit(self.member, self.data)
        self.data['picks'][0]['price'] = '2.5000'
        updated = submit(self.member, self.data)
        self.assertEqual(updated.expected_return, 75000)
        slip.refresh_from_db()
        self.assertEqual(slip.expected_return, 60000)
        self.assertEqual(slip.results.get(position=0).selection['price'], '2.0000')

    def test_singles_charge_each_leg_and_sum_exact_returns(self):
        self.data['mode'] = 'single'
        slip = submit(self.member, self.data)
        self.assertEqual((slip.total_stake, slip.expected_return, self.balance()), (20000, 50000, 80000))

    def test_changed_request_token_cannot_deduct_again(self):
        submit(self.member, self.data)
        self.data['stake'] = '20000'
        with self.assertRaises(ValidationError): submit(self.member, self.data)
        self.assertEqual(self.balance(), 90000)

    def test_bad_choices_and_amounts_leave_balance_untouched(self):
        variants = []
        for key, value in [('stake', '1000000'), ('stake', '1'), ('stake', True), ('mode', 'unknown'), ('picks', []), ('picks', self.data['picks'] * 2)]:
            variants.append({**self.data, key: value})
        for key, value in [('price', '99.0000'), ('market', 'h2h_lay'), ('point', '9'), ('eventId', 'unknown')]:
            item = deepcopy(self.data)
            item['picks'][0][key] = value
            variants.append(item)
        for item in variants:
            with self.subTest(item=item), self.assertRaises(ValidationError): submit(self.member, item)
        self.assertEqual(self.balance(), 100000)
        self.assertFalse(DemoSlip.objects.exists())

    def test_started_event_and_payout_limit_rejected(self):
        self.member.multi_payout = 50000
        self.member.save()
        with self.assertRaises(ValidationError): submit(self.member, self.data)
        self.member.multi_payout = None
        self.member.save()
        self.events[0]['startsAt'] = (timezone.now() - timedelta(seconds=1)).isoformat()
        self.snapshot.payload = {'items': self.events}
        self.snapshot.save()
        with self.assertRaises(ValidationError): submit(self.member, self.data)
        self.assertEqual(self.balance(), 100000)

    def test_ledger_failure_rolls_back_deduction_and_slip(self):
        with patch('sportsfeed.slips.entry', side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError): submit(self.member, self.data)
        self.assertEqual(self.balance(), 100000)
        self.assertFalse(DemoSlip.objects.exists())

    def test_auth_csrf_history_privacy_and_method(self):
        url = '/api/sports/slips/submit/'
        self.assertEqual(self.client.post(url).status_code, 401)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.member)
        response = self.client.post(url, json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['slip']['virtualOnly'])
        self.assertEqual(len(self.client.get('/api/sports/slips/').json()['items']), 1)
        other = get_user_model().objects.create_user(username='other_demo')
        self.client.force_login(other)
        self.assertEqual(self.client.get('/api/sports/slips/').json()['items'], [])
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.member)
        self.assertEqual(strict.post(url, json.dumps(self.data), content_type='application/json').status_code, 403)

    def test_suspension_is_checked_again_in_service(self):
        self.member.account_status = 'suspended'
        self.member.save()
        with self.assertRaises(ValidationError): submit(self.member, self.data)
        self.assertEqual(self.balance(), 100000)

    def test_cumulative_requests_cannot_overdraw(self):
        self.data['stake'] = '90000'
        submit(self.member, self.data)
        self.data['requestId'] = str(uuid4())
        with self.assertRaises(ValidationError): submit(self.member, self.data)
        self.assertEqual(self.balance(), 10000)
