from copy import deepcopy
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from zoneinfo import ZoneInfo
from .models import FeedSnapshot
from .portal_bridge import apply_results


class PortalBridgeTests(TestCase):
    def setUp(self):
        self.event={'id':'source-1','home':'LG Twins','away':'Doosan Bears','group':'Baseball','leagueKey':'baseball_kbo','startsAt':(timezone.now()-timedelta(hours=3)).isoformat(),'completed':False,'status':'unconfirmed','bookmakers':[{'old':'preserved'}]}
        self.day=timezone.now().astimezone(ZoneInfo('Asia/Seoul')).date().isoformat()
        from django.utils.dateparse import parse_datetime
        self.day=parse_datetime(self.event['startsAt']).astimezone(ZoneInfo('Asia/Seoul')).date().isoformat()
        self.result={'id':'portal1','home':'LG Twins','away':'Doosan Bears','status':'finished','scores':[4,1],'leaguePath':'/baseball/south-korea/kbo/','sourceDay':self.day,'url':'https://www.oddsportal.com/baseball/h2h/a/b/#portal1'}
        self.state=FeedSnapshot.objects.create(payload={'items':[self.event]})

    def test_verified_result_moves_to_results_without_changing_quotes(self):
        self.assertEqual(apply_results([self.result])['updated'],1)
        self.state.refresh_from_db();event=self.state.payload['items'][0]
        self.assertTrue(event['completed']);self.assertEqual(event['status'],'completed')
        self.assertEqual(event['bookmakers'],self.event['bookmakers'])
        self.assertEqual(event['scores'],[{'name':'LG Twins','score':'4'},{'name':'Doosan Bears','score':'1'}])
        self.assertEqual(apply_results([self.result])['updated'],0)

    def test_wrong_day_league_teams_and_nonfinal_do_not_close(self):
        for key,value in [('sourceDay','2000-01-01'),('leaguePath','/baseball/usa/mlb/'),('away','Other Bears'),('status','live'),('scores',[None,1])]:
            with self.subTest(key=key):self.assertEqual(apply_results([{**self.result,key:value}])['updated'],0)

    def test_double_header_ambiguity_is_not_guessed(self):
        second={**self.event,'id':'source-2'}
        self.state.payload={'items':[self.event,second]};self.state.save()
        self.assertEqual(apply_results([self.result])['updated'],0)
        self.state.payload={'items':[self.event]};self.state.save()
        self.assertEqual(apply_results([self.result,{**self.result,'id':'portal2'}])['updated'],0)
