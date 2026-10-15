from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import HarvesterJob,HarvesterSnapshot
from .harvester import CollectionForm,normalize,run_job


class BookmakerSelectionTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('bookmaker-qa')
        self.data={'sport':'football','mode':'upcoming','day':'2026-10-15T19:00','league':'all','market_set':'winner','limit':'10'}
        self.raw={'match_link':'https://www.oddsportal.com/football/h2h/home-team/away-team/#12345678','home_team':'Home','away_team':'Away','match_date':'2026-10-15 12:00:00 UTC','league_name':'League','1x2_market':[{'bookmaker_name':'bet365','period':'FullTime','1':'1.90','X':'3.10','2':'4.00'},{'bookmaker_name':'Other Book','period':'FullTime','1':'2.00','X':'3.20','2':'4.10'}]}
        self.job=HarvesterJob.objects.create(requested_by=self.user,mode='upcoming',sport='football',day=date(2026,10,15),markets='1x2',target_bookmaker='bet365')

    def test_presets_custom_and_all(self):
        form=CollectionForm({**self.data,'bookmaker':'bet365'})
        self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['target_bookmaker'],'bet365')
        form=CollectionForm({**self.data,'bookmaker':'custom','bookmaker_name':'  My Book  '})
        self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['target_bookmaker'],'My Book')
        self.assertFalse(CollectionForm({**self.data,'bookmaker':'custom'}).is_valid())
        form=CollectionForm(self.data);self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['target_bookmaker'],'')

    def test_selected_book_is_enforced_in_normalized_and_raw_data(self):
        event=normalize(self.raw,self.job)
        self.assertEqual([book['title'] for book in event['bookmakers']],['bet365'])
        self.assertEqual([row['bookmaker_name'] for row in event['raw']['1x2_market']],['bet365'])
        self.job.target_bookmaker='Absent Book'
        self.assertEqual(normalize(self.raw,self.job)['bookmakers'],[])

    @patch('sportsfeed.harvester.run_cli')
    def test_cli_receives_selected_book_only_for_details(self,cli):
        cli.side_effect=[([{'match_link':self.raw['match_link']}],0),([self.raw],0)]
        run_job(self.job.pk)
        self.assertNotIn('--target-bookmaker',cli.call_args_list[0].args[1])
        args=cli.call_args_list[1].args[1]
        self.assertEqual(args[args.index('--target-bookmaker')+1],'bet365')
        self.assertEqual(len(HarvesterSnapshot.objects.get().payload['items'][0]['bookmakers']),1)

    @patch('sportsfeed.harvester.run_cli')
    def test_all_books_does_not_add_cli_filter(self,cli):
        self.job.target_bookmaker='';self.job.save()
        cli.side_effect=[([{'match_link':self.raw['match_link']}],0),([self.raw],0)]
        run_job(self.job.pk)
        self.assertNotIn('--target-bookmaker',cli.call_args_list[1].args[1])
        self.assertEqual(len(HarvesterSnapshot.objects.get().payload['items'][0]['bookmakers']),2)

    @patch('sportsfeed.harvester.subprocess.Popen')
    def test_admin_post_persists_choice_and_history(self,popen):
        self.job.active_key=None;self.job.save()
        self.client.force_login(self.user)
        url=reverse('admin:sportsfeed_harvestersnapshot_changelist')
        self.client.post(url,{**self.data,'bookmaker':'bet365','action':'collect'})
        self.assertEqual(HarvesterJob.objects.latest('pk').target_bookmaker,'bet365')
        self.assertContains(self.client.get(url),'name="bookmaker"')
