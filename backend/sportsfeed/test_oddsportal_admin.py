import json
from io import StringIO
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from .models import OddsPortalCollectionJob as Job, OddsPortalSnapshot
from .oddsportal_jobs import start_job, run_job, expire_stale, launch_job


class CollectionAdminTests(TestCase):
    def test_pause_resume_permissions_and_persistence(self):
        import tempfile
        from pathlib import Path
        from .collector_control import is_paused
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'ODDSPORTAL_RUNTIME_DIR': folder}):
            url=reverse('admin:sportsfeed_oddsportal_toggle_results')
            self.assertEqual(self.client.get(url).status_code,405)
            self.assertEqual(self.client.post(url,{'action':'pause'}).status_code,302)
            self.assertTrue(is_paused())
            self.assertTrue(self.client.get(self.list).context['results_paused'])
            self.client.post(url,{'action':'resume'})
            self.assertFalse(is_paused())
            viewer=get_user_model().objects.create_user(username='pause_viewer',is_staff=True)
            viewer.user_permissions.add(Permission.objects.get(codename='view_oddsportalsnapshot'))
            self.client.force_login(viewer)
            self.assertEqual(self.client.post(url,{'action':'pause'}).status_code,403)
            self.assertFalse(Path(folder,'paused').exists())

    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='collector_admin',password=None)
        self.client.force_login(self.admin)
        self.start=reverse('admin:sportsfeed_oddsportal_collect_today')
        self.list=reverse('admin:sportsfeed_oddsportalsnapshot_changelist')

    @patch('sportsfeed.oddsportal_jobs.launch_job')
    def test_button_launch_duplicate_and_job_status(self,launch):
        self.assertContains(self.client.get(self.list),'오늘 경기 전체 수집')
        self.assertEqual(self.client.get(self.start).status_code,405)
        self.assertEqual(self.client.post(self.start).status_code,302)
        self.assertEqual(self.client.post(self.start).status_code,302)
        launch.assert_called_once()
        self.assertEqual(Job.objects.count(),1)
        job=Job.objects.get()
        self.assertEqual(job.requested_by,self.admin)
        self.assertIn('collection-status/',self.client.get(self.list).context['collection_status_url'])
        response=self.client.get(reverse('admin:sportsfeed_oddsportal_collection_status',args=[job.pk]))
        self.assertEqual(response.json()['status'],'queued')

    @patch('sportsfeed.oddsportal_jobs.launch_job')
    def test_view_only_cannot_trigger(self,launch):
        viewer=get_user_model().objects.create_user(username='viewer',is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_oddsportalsnapshot'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.list).status_code,200)
        self.assertNotContains(self.client.get(self.list),'id="collect-today"')
        self.assertEqual(self.client.post(self.start).status_code,403)
        self.assertFalse(Job.objects.exists())

    def test_csrf_and_ordinary_member(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(self.start).status_code,403)
        member=get_user_model().objects.create_user(username='member')
        client.force_login(member)
        self.assertEqual(client.get(self.list).status_code,302)
        self.assertFalse(Job.objects.exists())

    @patch('sportsfeed.oddsportal_jobs.launch_job',side_effect=OSError('cannot launch'))
    def test_launch_failure_releases_lock(self,launch):
        job,started=start_job(self.admin)
        self.assertTrue(started);job.refresh_from_db()
        self.assertEqual(job.status,'failed');self.assertIsNone(job.active_key)

    def test_expired_job_releases_lock(self):
        job=Job.objects.create(requested_by=self.admin,day=timezone.now().date())
        Job.objects.filter(pk=job.pk).update(updated_at=timezone.now()-timedelta(minutes=20))
        expire_stale();job.refresh_from_db()
        self.assertEqual(job.status,'failed');self.assertIsNone(job.active_key)

    @patch('sportsfeed.oddsportal_jobs.subprocess.Popen')
    def test_detached_worker_uses_server_database(self,popen):
        from django.conf import settings
        job=Job.objects.create(requested_by=self.admin,day=timezone.now().date())
        launch_job(job)
        args,kwargs=popen.call_args
        self.assertIn('collect_oddsportal_today',args[0])
        self.assertEqual(args[0][-1],str(job.pk))
        self.assertEqual(kwargs['env']['EVEPREVIEW_JOB_DATABASE'],str(settings.DATABASES['default']['NAME']))


class CollectionWorkerTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser(username='job_admin',password=None)
        self.job=Job.objects.create(requested_by=self.user,day=timezone.now().date())
        self.item=dict(id='12345678',home='Home',away='Away',url='https://www.oddsportal.com/football/h2h/a/b/#12345678',scores=[0,0],odds=['2','3','4'],status='finished')

    def run_events(self,events):
        proc=MagicMock();proc.stdout=StringIO(''.join(json.dumps(e)+'\n' for e in events));proc.wait.return_value=0;proc.poll.return_value=0
        with patch('sportsfeed.oddsportal_jobs.set_paused'),patch('sportsfeed.oddsportal_jobs.subprocess.Popen',return_value=proc):run_job(self.job.pk)
        self.job.refresh_from_db()

    def test_success_and_unique_match_count(self):
        report=dict(sport='football',count=1,complete=True)
        page=dict(type='page',completed=1,total=1,items=[self.item],report=report,collectionDay='2026-10-15',timezone='Asia/Seoul')
        self.run_events([dict(type='plan',total=1,reports=[]),page,dict(type='done',reports=[report])])
        self.assertEqual(self.job.status,'complete');self.assertEqual(self.job.match_count,1);self.assertIsNone(self.job.active_key)
        self.assertEqual(OddsPortalSnapshot.objects.get(pk=1).payload['items'][0]['scores'],[0,0])

    def test_partial_retains_success_and_reports_failures(self):
        good=dict(sport='football',count=1,complete=True)
        bad=dict(sport='tennis',count=0,complete=False,error='HTTP 503')
        self.run_events([dict(type='page',completed=1,total=2,items=[self.item],report=good,collectionDay='2026-10-15',timezone='Asia/Seoul'),dict(type='page',completed=2,total=2,items=[],report=bad),dict(type='done',reports=[good,bad])])
        self.assertEqual(self.job.status,'partial');self.assertEqual(self.job.pages_done,2)
        self.assertEqual(len(OddsPortalSnapshot.objects.get(pk=1).payload['items']),1)

    def test_fatal_does_not_replace_old_snapshot(self):
        OddsPortalSnapshot.objects.create(pk=1,payload={'items':[self.item]})
        self.run_events([dict(type='fatal',error='network failure')])
        self.assertEqual(self.job.status,'failed');self.assertIsNone(self.job.active_key)
        self.assertEqual(len(OddsPortalSnapshot.objects.get(pk=1).payload['items']),1)
