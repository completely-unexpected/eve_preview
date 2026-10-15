from unittest.mock import patch
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from wallet.models import MAX_AMOUNT, Wallet, WalletEntry
from .models import DemoLeg, DemoSlip
from .slips import submit, serialize
from .settlement import settle
from .test_slips import DemoSlipTests


class SettlementTests(DemoSlipTests):
    # Inherit submission regression checks against the new result rows as well.
    def setUp(self):
        super().setUp()
        self.operator = get_user_model().objects.create_superuser(username='demo_settler')

    def test_multi_won_pays_once_and_cannot_be_reversed(self):
        slip = submit(self.member, self.data)
        self.assertEqual(settle(slip.pk, self.operator, result='won'), 2)
        self.assertEqual(self.balance(), 150000)
        self.assertEqual(settle(slip.pk, self.operator, result='won'), 0)
        slip.refresh_from_db()
        self.assertEqual((slip.status, slip.credited_amount), ('won', 60000))
        self.assertIsNotNone(slip.settled_at)
        self.assertEqual(slip.settled_by, self.operator)
        self.assertEqual(WalletEntry.objects.filter(kind='demo_settlement').count(), 1)
        with self.assertRaises(ValidationError): settle(slip.pk, self.operator, result='void', position=0)
        self.assertEqual(self.balance(), 150000)

    def test_single_partial_win_loss_and_status(self):
        self.data['mode'] = 'single'
        slip = submit(self.member, self.data)
        settle(slip.pk, self.operator, result='won', position=0)
        self.assertEqual(self.balance(), 100000)
        slip.refresh_from_db()
        self.assertEqual(slip.status, 'pending')
        settle(slip.pk, self.operator, result='lost', position=1)
        self.assertEqual(self.balance(), 100000)
        slip.refresh_from_db()
        self.assertEqual((slip.status, slip.credited_amount), ('mixed', 20000))
        self.assertEqual(serialize(slip)['legs'][1]['result'], 'lost')

    def test_void_refunds_single_and_multi_exactly_once(self):
        for mode in ('single', 'multi'):
            self.data['mode'] = mode
            self.data['requestId'] = __import__('uuid').uuid4().hex
            slip = submit(self.member, self.data)
            settle(slip.pk, self.operator, result='void')
            self.assertEqual(self.balance(), 100000)
            settle(slip.pk, self.operator, result='void')
            self.assertEqual(self.balance(), 100000)

    def test_multi_void_leg_excluded_and_loss_zero(self):
        slip = submit(self.member, self.data)
        settle(slip.pk, self.operator, result='void', position=0)
        self.assertEqual(self.balance(), 90000)
        settle(slip.pk, self.operator, result='won', position=1)
        self.assertEqual(self.balance(), 120000)
        slip.refresh_from_db()
        self.assertEqual(slip.credited_amount, 30000)
        self.data['requestId'] = __import__('uuid').uuid4().hex
        slip = submit(self.member, self.data)
        settle(slip.pk, self.operator, result='lost', position=0)
        settle(slip.pk, self.operator, result='won', position=1)
        self.assertEqual(self.balance(), 110000)
        slip.refresh_from_db()
        self.assertEqual((slip.status, slip.credited_amount), ('lost', 0))

    def test_permissions_and_unknown_result(self):
        slip = submit(self.member, self.data)
        with self.assertRaises(ValidationError): settle(slip.pk, self.member, result='won')
        with self.assertRaises(ValidationError): settle(slip.pk, self.operator, result='bogus')
        self.operator.is_active = False
        with self.assertRaises(ValidationError): settle(slip.pk, self.operator, result='won')
        self.assertEqual(self.balance(), 90000)

    def test_wallet_cap_and_audit_failure_roll_back_everything(self):
        slip = submit(self.member, self.data)
        Wallet.objects.filter(pk=self.wallet.pk).update(available=MAX_AMOUNT)
        with self.assertRaises(ValidationError): settle(slip.pk, self.operator, result='won')
        self.assertFalse(slip.results.exclude(result='pending').exists())
        Wallet.objects.filter(pk=self.wallet.pk).update(available=90000)
        with patch('sportsfeed.settlement.entry', side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError): settle(slip.pk, self.operator, result='won')
        self.assertEqual(self.balance(), 90000)
        self.assertFalse(slip.results.exclude(result='pending').exists())
        slip.refresh_from_db()
        self.assertEqual(slip.status, 'pending')

    def test_admin_actions_exist_and_form_is_read_only(self):
        self.client.force_login(self.operator)
        slip = submit(self.member, self.data)
        url = '/admin/sportsfeed/demoslip/'
        response = self.client.get(url)
        self.assertContains(response, 'mark_won')
        response = self.client.post(url, {'action': 'mark_void', '_selected_action': str(slip.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.balance(), 100000)
        response = self.client.post(url, {'action': 'mark_void', '_selected_action': str(slip.pk)})
        self.assertEqual(self.balance(), 100000)
        response = self.client.get(f'/admin/sportsfeed/demoslip/{slip.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(self.client.get('/admin/sportsfeed/demoleg/').status_code, 200)
