from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from .models import FeedSnapshot
from .refresh import refresh_soccer
from .services import ProviderError

class SoccerRefreshTests(TestCase):
    def setUp(self):
        self.catalog=[{'key':'soccer_epl','title':'EPL','group':'Soccer','active':True}, {'key':'soccer_other','title':'Other','group':'Soccer','active':True}, {'key':'basketball_test','title':'Basketball','group':'Basketball','active':True}]
        self.old={'id':'old','home':'Home','away':'Away','leagueKey':'soccer_epl','group':'Soccer','startsAt':(timezone.now()-timedelta(hours=1)).isoformat(),'completed':False}
        self.basket={'id':'basket','leagueKey':'basketball_test','startsAt':(timezone.now()+timedelta(days=1)).isoformat(),'group':'Basketball','bookmakers':[{'test':'unchanged'}]}
        self.snapshot=FeedSnapshot.objects.create(pk=1,payload={'items':[self.old,self.basket],'complete':True})

    @patch('sportsfeed.refresh.request_json')
    def test_refresh_preserves_other_sports_and_updates_closed_scores(self,fetch):
        event={'id':'new','home_team':'Home','away_team':'Away','commence_time':(timezone.now()+timedelta(days=1)).isoformat()}
        fetch.side_effect=[(self.catalog,{'remaining':10}),([event],{}),([event],{'remaining':7}),([{'id':'old','completed':True,'scores':[{'name':'Home','score':'2'},{'name':'Away','score':'1'}]}],{'remaining':5}),([],{}),([],{'remaining':2})]
        result=refresh_soccer()
        data={e['id']:e for e in result.payload['items']}
        self.assertEqual(data['basket'],self.basket)
        self.assertTrue(data['old']['completed'])
        self.assertEqual(data['old']['scores'][0]['score'],'2')
        self.assertIn('new',data)
        self.assertEqual(result.payload['remainingCredits'],2)
        self.assertEqual(len(result.payload['lastRefresh']['leagues']),2)
        self.assertFalse(FeedSnapshot.objects.get().syncing)

    @patch('sportsfeed.refresh.request_json')
    def test_low_budget_preserves_old_data_without_paid_calls(self,fetch):
        fetch.return_value=(self.catalog,{'remaining':5})
        with self.assertRaises(ProviderError):refresh_soccer()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.payload['items'],[self.old,self.basket])
        self.assertFalse(self.snapshot.syncing)
        self.assertEqual(fetch.call_count,1)

    @patch('sportsfeed.refresh.request_json')
    def test_odds_reserve_skips_scores_when_budget_tight(self,fetch):
        fetch.side_effect=[(self.catalog,{'remaining':6}),([],{}),([],{'remaining':3}),([],{}),([],{'remaining':0})]
        result=refresh_soccer()
        self.assertEqual(result.payload['lastRefresh']['scoreLeagues'],[])
        self.assertEqual(result.payload['remainingCredits'],0)
