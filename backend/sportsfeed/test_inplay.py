from datetime import datetime,UTC
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .harvester import CollectionForm,InplayForm,upcoming_selected,plans_for,merge
from .models import HarvesterJob,HarvesterSnapshot,InplaySnapshot
from .parsing_options import ParsingForm,filter_items


class InplaySeparationTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('inplay-test-admin')
        self.client.force_login(self.user)
        self.data={'sport':'football','mode':'upcoming','day':'2026-10-15T18:30','league':'all','market_set':'winner','limit':'10'}

    def test_korean_datetime_and_boundary(self):
        form=CollectionForm(self.data);self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['starts_from'].astimezone(UTC),datetime(2026,10,15,9,30,tzinfo=UTC))
        job=HarvesterJob(pk=1,sport='football',mode='upcoming',day=form.cleaned_data['day'],starts_from=form.cleaned_data['starts_from'],league='all',markets='1x2',limit=10)
        plan=next(plans_for(job))
        self.assertFalse(upcoming_selected({'kickoff_utc':'2026-10-15 09:29:00 UTC'},plan))
        self.assertTrue(upcoming_selected({'kickoff_utc':'2026-10-15 09:30:00 UTC'},plan))
        self.assertFalse(upcoming_selected({'kickoff_utc':'2026-10-16 09:30:00 UTC'},plan))

    def test_normal_collectors_do_not_offer_or_include_inplay(self):
        self.assertNotIn('live',dict(CollectionForm().fields['mode'].choices))
        self.assertNotIn('live',dict(ParsingForm().fields['status'].choices))
        self.assertEqual(filter_items([{'sport':'football','status':'live'}],{'status':'all'}),[])
        bad=CollectionForm({**self.data,'mode':'live'});self.assertFalse(bad.is_valid())

    @patch('sportsfeed.harvester.subprocess.Popen')
    def test_dedicated_page_creates_live_job_and_separate_storage(self,popen):
        url=reverse('admin:sportsfeed_inplay_collect')
        response=self.client.get(url)
        self.assertContains(response,'Inplay 수집 시작')
        self.assertNotContains(response,'name="mode"');self.assertNotContains(response,'name="day"')
        self.client.post(url,{**self.data,'action':'collect'})
        job=HarvesterJob.objects.get();self.assertEqual(job.mode,'live');self.assertIsNone(job.starts_from)
        merge([{'id':'inplay-test','status':'live','home':'Home','away':'Away'}],job)
        self.assertEqual(len(InplaySnapshot.objects.get().payload['items']),1)
        self.assertFalse(HarvesterSnapshot.objects.exists())

    def test_form_does_not_need_date_or_mode(self):
        data={key:self.data[key] for key in ('sport','league','market_set','limit')}
        form=InplayForm(data);self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['mode'],'live')
