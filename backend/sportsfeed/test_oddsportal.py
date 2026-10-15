import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from .models import OddsPortalSnapshot


class OddsPortalTests(TestCase):
    def setUp(self):
        pause=patch('sportsfeed.collector_control.is_paused',return_value=False)
        pause.start()
        self.addCleanup(pause.stop)

    def collect(self,items):
        with patch('sportsfeed.management.commands.sync_oddsportal.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'source':'OddsPortal','items':items}),stderr='')):
            call_command('sync_oddsportal',stdout=StringIO())

    def item(self):
        return dict(id='testAB12',home='Home',away='Away',url='https://www.oddsportal.com/football/h2h/home/away/#testAB12',status='finished',statusText='Finished',scores=[0,0],odds=['2.10','3.20','4.00'])

    def test_save_zero_score_and_public_read(self):
        self.collect([self.item()])
        data=self.client.get('/api/sports/oddsportal/?scope=all').json()
        self.assertEqual(data['items'][0]['scores'],[0,0])
        self.assertEqual(data['source'],'OddsPortal')
        self.assertIn('no-store',self.client.get('/api/sports/oddsportal/').headers['Cache-Control'])

    def test_update_same_id_without_duplicates(self):
        item=self.item();item['status']='live';self.collect([item])
        self.collect([self.item()])
        items=OddsPortalSnapshot.objects.get(pk=1).payload['items']
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['status'],'finished')

    def test_failure_keeps_last_data(self):
        self.collect([self.item()])
        old=OddsPortalSnapshot.objects.get(pk=1).fetched_at
        with self.assertRaises(CommandError):self.collect([])
        state=OddsPortalSnapshot.objects.get(pk=1)
        self.assertEqual(state.fetched_at,old)
        self.assertEqual(len(state.payload['items']),1)
        self.assertTrue(state.last_error)

    def test_identity_collision_retains_previous(self):
        self.collect([self.item()])
        item=self.item();item['home']='Different'
        with self.assertRaises(CommandError):self.collect([item])
        self.assertEqual(OddsPortalSnapshot.objects.get(pk=1).payload['items'][0]['home'],'Home')

    def test_completed_removed_but_live_zero_score_kept(self):
        finished=self.item()
        live={**finished,'id':'liveAB12','status':'live'}
        cancelled={**finished,'id':'cancel12','status':'cancelled'}
        self.collect([finished,live,cancelled])
        data=self.client.get('/api/sports/oddsportal/').json()
        self.assertEqual([item['id'] for item in data['items']],['liveAB12'])
        self.assertEqual(data['resultCount'],1)
        self.assertEqual(self.client.get('/api/sports/oddsportal/?scope=results').json()['items'][0]['id'],finished['id'])
        self.assertEqual(len(OddsPortalSnapshot.objects.get(pk=1).payload['items']),3)

    def test_stale_update_does_not_reopen_finished(self):
        self.collect([self.item()])
        item=self.item();item['status']='scheduled';item['scores']=None
        self.collect([item])
        self.assertEqual(self.client.get('/api/sports/oddsportal/').json()['items'],[])
        self.assertEqual(OddsPortalSnapshot.objects.get(pk=1).payload['items'][0]['scores'],[0,0])
