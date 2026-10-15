from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .parsing_options import ParsingForm,filter_items
from .models import OddsPortalCollectionJob


class ParsingOptionsTests(TestCase):
    def test_every_selector_has_all(self):
        form=ParsingForm({'sport':'all','league':'all','status':'all','odds':'all','limit':'0'})
        self.assertTrue(form.is_valid(),form.errors)
        for field in form.fields.values(): self.assertIn('전체',[label for key,label in field.choices])

    def test_status_odds_and_limit_apply_to_saved_rows(self):
        rows=[{'id':'a','sport':'football','status':'finished','odds':['1.95']},{'id':'b','sport':'football','status':'upcoming','odds':[]},{'id':'c','sport':'football','status':'upcoming','odds':['2.10']}]
        self.assertEqual([r['id'] for r in filter_items(rows,{'status':'upcoming','odds':'with'})],['c'])
        self.assertEqual(len(filter_items(rows,{'status':'all','odds':'all'},remaining=1)),1)
        self.assertEqual(filter_items(rows,{'sport':'basketball'}),[])

    @patch('sportsfeed.oddsportal_jobs.launch_job')
    def test_admin_saves_collection_options(self,launch):
        user=get_user_model().objects.create_superuser('parsing-options-admin')
        self.client.force_login(user)
        response=self.client.get(reverse('admin:sportsfeed_oddsportalsnapshot_changelist'))
        self.assertContains(response,'OddsParsing 수집 실행')
        self.assertEqual(self.client.post(reverse('admin:sportsfeed_oddsportal_collect_today'),{'sport':'football','league':'all','status':'finished','odds':'all','limit':'20'}).status_code,302)
        self.assertEqual(OddsPortalCollectionJob.objects.get().options['status'],'finished')
        self.assertEqual(OddsPortalCollectionJob.objects.get().options['limit'],20)
