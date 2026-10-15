from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase
from .harvester import CollectionForm, InplayForm, representative_event, collect_representative


class RepresentativeTests(SimpleTestCase):
    def setUp(self):
        self.plan=SimpleNamespace(day=date(2026,10,15),sport='football',mode='upcoming',starts_from=datetime(2026,10,15,19,tzinfo=ZoneInfo('Asia/Seoul')),limit=10)
        self.row={'url':'https://www.oddsportal.com/football/h2h/home/away/#12345678','home':'Home','away':'Away','status':'scheduled','statusText':'20:00','odds':['1.90',None,'4.00'],'leagueText':'League','sourcePage':'https://www.oddsportal.com/matches/football/20261015/'}

    def test_preserves_columns_without_inventing_a_bookmaker_or_market(self):
        event=representative_event(self.row,self.plan)
        market=event['bookmakers'][0]['markets'][0]
        self.assertEqual(market['key'],'portal_display')
        self.assertEqual([o['displayColumn'] for o in market['outcomes']],[0,2])
        self.assertEqual([o['price'] for o in market['outcomes']],[1.9,4.0])
        self.assertFalse(event['provenance']['bookmakerIdentified'])
        self.assertEqual(event['raw']['odds'],['1.90',None,'4.00'])
        self.assertEqual(event['startsAt'],'2026-10-15T11:00:00+00:00')

    def test_cutoff_status_and_final_scores(self):
        self.assertIsNone(representative_event({**self.row,'statusText':'18:00'},self.plan))
        self.assertIsNone(representative_event({**self.row,'status':'live'},self.plan))
        self.plan.mode='historic'
        event=representative_event({**self.row,'status':'finished','scores':[2,1]},self.plan)
        self.assertTrue(event['completed'])
        with self.assertRaises(ValueError): representative_event({**self.row,'status':'finished'},self.plan)

    def test_option_validation(self):
        data={'sport':'football','mode':'historic','day':'2026-10-15T19:00','league':'all','market_set':'all','bookmaker':'OddsPortal (listing)','limit':'10'}
        form=CollectionForm(data)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(InplayForm(data).is_valid())
        self.assertFalse(CollectionForm({**data,'league':'football/england/premier-league'}).is_valid())

    def test_listing_dispatch_does_not_request_bookmaker_details(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as folder, patch('sportsfeed.harvester.run_cli',return_value=([self.row],0)) as cli:
            result=collect_representative(SimpleNamespace(league='all'),self.plan,Path(folder))
        self.assertEqual(len(result),1)
        self.assertEqual(cli.call_args.args[1],[])
        self.assertIn('representative.cjs',cli.call_args.kwargs['command_override'][1])
