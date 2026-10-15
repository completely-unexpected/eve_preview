from copy import deepcopy
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase
from wallet.models import Wallet, WalletEntry
from .models import DemoLeg, DemoSlip, PowerballResult, PowerballSync
from .powerball import KST, current_board
from .powerball_results import save_results, sync_results
from .slips import submit


class PowerballResultTests(TestCase):
    def test_display_outcomes_match_settlement_at_boundaries(self):
        from types import SimpleNamespace
        from .powerball_outcomes import outcomes
        from .powerball_results import result_for
        for total,expected in [(15,'소 (15~64)'),(64,'소 (15~64)'),(65,'중 (65~80)'),(80,'중 (65~80)'),(81,'대 (81~130)'),(130,'대 (81~130)')]:
            for power in (0,4,5,9):
                result=SimpleNamespace(balls=[total],powerball=power)
                values=outcomes(result)
                self.assertEqual(values['general_range'],expected)
                self.assertEqual(values['power_range'],'언더 (0~4)' if power<=4 else '오버 (5~9)')
                self.assertEqual(values['power_parity'],'홀' if power%2 else '짝')
                for market,name in values.items(): self.assertEqual(result_for({'market':market,'name':name},result),'won')

    def setUp(self):
        self.now=datetime(2026,10,15,10,17,tzinfo=KST)
        self.after=datetime(2026,10,15,10,26,tzinfo=KST)
        self.member=get_user_model().objects.create_user(username='automatic_member')
        self.wallet=Wallet.objects.create(member=self.member,available=100000)
        self.result={'reg_date':'2026-10-15','date_round':124,'round':451420,'ball_1':1,'ball_2':2,'ball_3':3,'ball_4':4,'ball_5':5,'powerball':4}

    def slip(self,multi=False):
        events=current_board(self.now)['items'][:2 if multi else 1]
        data={'requestId':str(uuid4()),'mode':'multi' if multi else 'single','stake':'10000','picks':[{'eventId':e['id'],'bookKey':'simulation','market':'general_parity',**e['bookmakers'][0]['markets'][0]['outcomes'][0]} for e in events]}
        with patch('django.utils.timezone.now',return_value=self.now):return submit(self.member,data,source='powerball')

    def test_official_result_settles_once_with_audited_unusable_account(self):
        slip=self.slip()
        with patch('django.utils.timezone.now',return_value=self.after),patch('sportsfeed.powerball_results.read_results',return_value=[self.result]):
            self.assertEqual(sync_results()['settled'],1)
            self.assertEqual(sync_results(force=True)['settled'],0)
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,109500)
        slip.refresh_from_db();self.assertEqual(slip.status,'won')
        actor=get_user_model().objects.get(username='ntry_result_worker')
        self.assertFalse(actor.has_usable_password());self.assertFalse(actor.is_superuser)
        self.assertEqual(WalletEntry.objects.filter(kind='demo_settlement').count(),1)

    def test_multi_waits_for_all_matching_rounds(self):
        slip=self.slip(multi=True)
        with patch('django.utils.timezone.now',return_value=self.after),patch('sportsfeed.powerball_results.read_results',return_value=[self.result]):sync_results()
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,90000)
        second={**self.result,'date_round':125,'round':451421}
        with patch('django.utils.timezone.now',return_value=self.after),patch('sportsfeed.powerball_results.read_results',return_value=[self.result,second]):sync_results(force=True)
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,128025)
        slip.refresh_from_db();self.assertEqual(slip.credited_amount,38025)

    def test_wrong_day_does_not_settle_same_round_number(self):
        slip=self.slip();old={**self.result,'reg_date':'2026-10-14'}
        with patch('django.utils.timezone.now',return_value=self.after),patch('sportsfeed.powerball_results.read_results',return_value=[old]):sync_results()
        slip.refresh_from_db();self.assertEqual(slip.status,'pending')
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,90000)

    def test_invalid_feed_batch_is_atomic(self):
        for key,value in [('ball_5',4),('powerball',10),('date_round',289),('ball_1',True),('reg_date','2099-01-01')]:
            invalid={**self.result,key:value,'round':451421,'date_round':125 if key!='date_round' else value}
            with self.subTest(key=key),patch('django.utils.timezone.now',return_value=self.after),self.assertRaises((ValueError,KeyError)):
                save_results([self.result,invalid])
            self.assertFalse(PowerballResult.objects.exists())

    def test_conflicting_correction_stops_and_preserves_saved_result(self):
        slip=self.slip()
        with patch('django.utils.timezone.now',return_value=self.after):save_results([self.result])
        corrected={**self.result,'powerball':8}
        with patch('django.utils.timezone.now',return_value=self.after),patch('sportsfeed.powerball_results.read_results',return_value=[corrected]),self.assertRaises(ValueError):sync_results(force=True)
        self.assertEqual(PowerballResult.objects.get().powerball,4)
        slip.refresh_from_db();self.assertEqual(slip.status,'pending')
        self.assertTrue(PowerballSync.objects.get().last_error)

    def test_disabled_sync_never_fetches_or_settles(self):
        self.slip();PowerballSync.objects.create(pk=1,enabled=False)
        with patch('sportsfeed.powerball_results.read_results') as fetch:self.assertTrue(sync_results()['disabled']);fetch.assert_not_called()
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,90000)

    def test_network_failure_does_not_change_pending_result(self):
        slip=self.slip()
        with patch('sportsfeed.powerball_results.read_results',side_effect=TimeoutError('timeout')),self.assertRaises(ValueError):sync_results()
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,90000)
        self.assertTrue(slip.results.filter(result='pending').exists())
        self.assertFalse(PowerballSync.objects.get().syncing)

    def test_losing_choice_is_zero_credit(self):
        slip=self.slip();even={**self.result,'ball_5':6}
        with patch('django.utils.timezone.now',return_value=self.after),patch('sportsfeed.powerball_results.read_results',return_value=[even]):sync_results()
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,90000)
        slip.refresh_from_db();self.assertEqual((slip.status,slip.credited_amount),('lost',0))

    def test_board_shows_public_results_without_member_details(self):
        with patch('django.utils.timezone.now',return_value=self.after):save_results([self.result])
        response=self.client.get('/api/games/powerball/board/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['results'][0]['powerball'],4)
        self.assertNotContains(response,'automatic_member')
