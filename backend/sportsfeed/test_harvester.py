from copy import deepcopy
from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from .models import HarvesterJob, HarvesterSnapshot, OddsPortalSnapshot, FeedSnapshot
from .harvester import CollectionForm, normalize, merge, safe_link, start_job, run_job,plans_for


class HarvesterTests(TestCase):
    def test_all_options_expand_to_real_collection_plans(self):
        form=CollectionForm({'sport':'all','mode':'all','day':'2026-10-15','league':'all','market_set':'all','limit':'0'})
        self.assertTrue(form.is_valid(),form.errors)
        for field in ('sport','mode','league','market_set','limit'):
            self.assertIn('전체',[str(label) for _,label in form.fields[field].choices])
        from types import SimpleNamespace
        plans=list(plans_for(SimpleNamespace(pk=1,sport='all',mode='all',league='all',markets='all',day=date.today(),limit=0)))
        self.assertEqual({p.mode for p in plans},{'upcoming','historic'})
        self.assertGreaterEqual(len({p.sport for p in plans}),11)
        self.assertTrue(all(p.markets and p.sport!='all' and p.mode!='all' for p in plans))

    def setUp(self):
        self.user=get_user_model().objects.create_superuser('harvester-qa',password='test-only-password')
        self.job=HarvesterJob.objects.create(requested_by=self.user,mode='upcoming',sport='football',day=date(2026,10,15),markets='1x2')
        self.raw={'match_link':'https://www.oddsportal.com/football/h2h/home-team/away-team/#abc12345','home_team':'Home','away_team':'Away','match_date':'2026-10-15 12:00:00 UTC','league_name':'Premier League','home_score':'1','away_score':'0','1x2_market':[{'bookmaker_name':'Example Book','period':'FullTime','1':'1.95','X':'3.10','2':'4.00','blocked_outcomes':['2']}]}

    def test_normalizes_prices_and_preserves_raw_without_guessing_final(self):
        event=normalize(self.raw,self.job)
        self.assertEqual(event['startsAt'],'2026-10-15T12:00:00+00:00')
        self.assertFalse(event['completed'])
        self.assertEqual(event['raw'],self.raw)
        self.assertEqual([o['name'] for o in event['bookmakers'][0]['markets'][0]['outcomes']],['Home','Draw'])
        self.job.mode='historic'
        self.assertTrue(normalize(self.raw,self.job)['completed'])
        self.raw.update(live_period='45',live_score_home=1,live_score_away=0)
        self.assertFalse(normalize(self.raw,self.job)['completed'])

    def test_store_is_separate_and_final_cannot_reopen(self):
        FeedSnapshot.objects.create(payload={'items':[{'id':'old-feed'}]})
        OddsPortalSnapshot.objects.create(payload={'items':[{'id':'old-portal'}]})
        self.job.mode='historic';final=normalize(self.raw,self.job);merge([final],self.job)
        self.job.mode='upcoming';merge([normalize(self.raw,self.job)],self.job)
        self.assertTrue(HarvesterSnapshot.objects.get().payload['items'][0]['completed'])
        self.assertEqual(FeedSnapshot.objects.get().payload['items'][0]['id'],'old-feed')
        self.assertEqual(OddsPortalSnapshot.objects.get().payload['items'][0]['id'],'old-portal')

    def test_rejects_arbitrary_links_and_invalid_options(self):
        for link in ['https://example.com/','http://127.0.0.1/','https://www.oddsportal.com/football/#abc']:
            with self.assertRaises(ValueError): safe_link(link)
        form=CollectionForm({'sport':'football','mode':'historic','day':'2026-10-15','league':'','market_set':'winner','limit':'10000'})
        self.assertFalse(form.is_valid());self.assertIn('league',form.errors);self.assertIn('limit',form.errors)

    def test_handicap_and_tennis_labels(self):
        self.raw['asian_handicap_-0_5_market']=[{'bookmaker_name':'Example Book','period':'FullTime','team1_handicap':'1.80','team2_handicap':'2.10'}]
        markets=normalize(self.raw,self.job)['bookmakers'][0]['markets']
        spread=next(m for m in markets if m['key']=='spreads')
        self.assertEqual([o['point'] for o in spread['outcomes']],[-0.5,0.5])
        self.raw['match_winner_market']=[{'bookmaker_name':'Example Book','period':'FullTime','player_1':'1.40','player_2':'2.90'}]
        self.assertEqual(len(normalize(self.raw,self.job)['bookmakers'][0]['markets']),3)

    @patch('sportsfeed.harvester.subprocess.Popen')
    def test_duplicate_job_does_not_spawn(self,spawn):
        data={'sport':'football','mode':'upcoming','day':date.today(),'league':'','markets':'1x2','limit':1}
        job,started=start_job(self.user,data)
        self.assertFalse(started);self.assertEqual(job.pk,self.job.pk);spawn.assert_not_called()

    def test_admin_permissions_stop_and_display(self):
        url=reverse('admin:sportsfeed_harvestersnapshot_changelist')
        self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(self.user)
        response=self.client.get(url)
        self.assertContains(response,'Harvester 수집 시작')
        self.assertEqual(self.client.post(url,{'action':'stop'}).status_code,302)
        self.job.refresh_from_db();self.assertEqual(self.job.status,'cancelled');self.assertIsNone(self.job.active_key)
        self.user.is_superuser=False;self.user.is_staff=True;self.user.save()
        self.assertEqual(self.client.post(url,{'action':'collect'}).status_code,403)

    def test_combined_admin_includes_separate_source(self):
        merge([normalize(self.raw,self.job)],self.job)
        self.client.force_login(self.user)
        response=self.client.get(reverse('admin:catalog_game_odds'),{'source':'harvester'})
        self.assertContains(response,'Home');self.assertContains(response,'1.95')

    @patch('sportsfeed.harvester.run_cli')
    def test_worker_saves_data_and_reports_missing_prices(self,cli):
        raw=deepcopy(self.raw);raw['1x2_market']=[]
        cli.side_effect=[([{'match_link':raw['match_link']}],0),([raw],0)]
        run_job(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status,'partial')
        self.assertEqual(self.job.match_count,1)
        self.assertIn('업체별 배당이 없는 경기 1개',self.job.error)
        self.assertEqual(len(HarvesterSnapshot.objects.get().payload['items']),1)
        self.assertFalse(FeedSnapshot.objects.exists());self.assertFalse(OddsPortalSnapshot.objects.exists())

    @patch('sportsfeed.harvester.run_cli')
    def test_cancel_during_collection_cannot_be_reactivated(self,cli):
        def stop(*args):
            HarvesterJob.objects.filter(pk=self.job.pk).update(status='cancelled',active_key=None)
            return [{'match_link':self.raw['match_link']}],0
        cli.side_effect=stop
        run_job(self.job.pk)
        self.job.refresh_from_db();self.assertEqual(self.job.status,'cancelled')
        self.assertFalse(HarvesterSnapshot.objects.exists());self.assertEqual(cli.call_count,1)

    @patch('sportsfeed.harvester.run_cli')
    def test_historic_requires_actual_final_score(self,cli):
        self.job.mode='historic';self.job.league='football/england/premier-league';self.job.save()
        raw=deepcopy(self.raw);raw['home_score']=None;raw['away_score']=None
        cli.side_effect=[([{'match_link':raw['match_link']}],0),([raw],0)]
        run_job(self.job.pk);self.job.refresh_from_db()
        self.assertEqual(self.job.status,'partial');self.assertEqual(self.job.match_count,0)
        self.assertEqual(HarvesterSnapshot.objects.get().payload['items'],[])

    def test_csrf_protects_collection_post(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(reverse('admin:sportsfeed_harvestersnapshot_changelist'),{'action':'stop'}).status_code,403)

    def test_harvester_inline_odds_and_result_lock(self):
        from catalog.odds import choices
        event=normalize(self.raw,self.job);merge([event],self.job)
        self.client.force_login(self.user)
        url=reverse('admin:catalog_game_odds')+'?source=harvester&event='+event['id']
        key=next(choices(event,'harvester'))[0]
        self.assertEqual(self.client.post(url,{'inline':'1','key':key,'value':'2.15'}).status_code,200)
        self.job.mode='historic';merge([normalize(self.raw,self.job)],self.job)
        self.assertEqual(self.client.post(url,{'inline':'1','key':key,'value':'2.20'}).status_code,409)
        result=self.client.get(reverse('admin:catalog_game_odds'),{'source':'harvester','status':'results'})
        self.assertContains(result,'Home');self.assertNotContains(result,'class="edit-odd"')
