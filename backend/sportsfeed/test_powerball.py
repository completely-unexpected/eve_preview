from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from catalog.models import Game
from wallet.models import Wallet
from .models import DemoSlip
from .powerball import KST, current_board
from .slips import submit
from .settlement import settle


class PowerballTests(TestCase):
    def setUp(self):
        Game.objects.update_or_create(slug='powerball', defaults={'name':'파워볼','category':'ball','is_published':True})
        self.now=datetime(2026,10,15,10,17,0,tzinfo=KST)
        self.member=get_user_model().objects.create_user(username='powerball_member')
        self.wallet=Wallet.objects.create(member=self.member, available=100000)

    def data(self, two=False):
        events=current_board(self.now)['items'][:2 if two else 1]
        return {'requestId':str(uuid4()),'mode':'single','stake':'10000','picks':[{
            'eventId':e['id'],'bookKey':'simulation','market':'general_parity',
            **e['bookmakers'][0]['markets'][0]['outcomes'][0]} for e in events]}

    def test_schedule_and_midnight_rollover(self):
        rounds=current_board(self.now)['items']
        self.assertEqual([e['round'] for e in rounds],[124,125,126])
        self.assertEqual(rounds[0]['closesAt'],'2026-10-15T10:19:05+09:00')
        rounds=current_board(datetime(2026,10,15,23,58,tzinfo=KST))['items']
        self.assertEqual([e['round'] for e in rounds],[288,1,2])
        self.assertEqual(rounds[1]['day'],'2026-10-16')

    def test_single_deduction_duplicate_and_manual_settlement(self):
        data=self.data()
        with patch('django.utils.timezone.now',return_value=self.now):
            slip=submit(self.member,data,source='powerball')
            self.assertEqual(submit(self.member,data,source='powerball').pk,slip.pk)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available,90000)
        self.assertEqual(slip.expected_return,19500)
        operator=get_user_model().objects.create_superuser(username='powerball_operator')
        settle(slip.pk,operator,result='won')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available,109500)

    def test_multi_quote_is_exact_and_multiple_choices_in_same_round_rejected(self):
        data=self.data(two=True);data['mode']='multi'
        with patch('django.utils.timezone.now',return_value=self.now):
            slip=submit(self.member,data,source='powerball')
            self.assertEqual((slip.total_stake,slip.expected_return),(10000,38025))
            data['requestId']=str(uuid4());data['picks'][1]=deepcopy(data['picks'][0])
            with self.assertRaises(ValidationError):submit(self.member,data,source='powerball')

    def test_closed_changed_and_forged_choices_do_not_deduct(self):
        original=self.data()
        with patch('django.utils.timezone.now',return_value=self.now.replace(minute=19,second=6)):
            with self.assertRaises(ValidationError):submit(self.member,original,source='powerball')
        for key,value in [('price','99.0000'),('name','forged'),('market','unknown')]:
            data=deepcopy(original);data['picks'][0][key]=value
            with patch('django.utils.timezone.now',return_value=self.now),self.assertRaises(ValidationError):submit(self.member,data,source='powerball')
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,100000)
        self.assertFalse(DemoSlip.objects.exists())

    def test_public_board_private_history_and_disabled_game(self):
        self.assertEqual(self.client.get('/api/games/powerball/board/').status_code,200)
        self.assertEqual(self.client.post('/api/games/powerball/board/').status_code,405)
        self.assertEqual(self.client.get('/api/games/powerball/slips/').status_code,401)
        self.client.force_login(self.member)
        with patch('django.utils.timezone.now',return_value=self.now):
            response=self.client.post('/api/games/powerball/submit/',json.dumps(self.data()),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(self.client.get('/api/games/powerball/slips/').json()['items']),1)
        self.assertEqual(self.client.get('/api/sports/slips/').json()['items'],[])
        other=get_user_model().objects.create_user(username='other_powerball');self.client.force_login(other)
        self.assertEqual(self.client.get('/api/games/powerball/slips/').json()['items'],[])
        Game.objects.filter(slug='powerball').update(is_published=False)
        self.assertEqual(self.client.get('/api/games/powerball/board/').status_code,404)
        with patch('django.utils.timezone.now',return_value=self.now),self.assertRaises(ValidationError):submit(other,self.data(),source='powerball')
