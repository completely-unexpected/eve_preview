import json
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.test import TestCase, Client
from wallet.models import Wallet
from catalog.models import Game
from .models import ActivityLog
from .tracking import context


class ActivityTests(TestCase):
    def test_ip_updates_on_authenticated_requests_without_changing_location(self):
        from .models import PagePresence
        from .pages import touch
        touch(self.user.username,'member','#/sports')
        self.client.get('/api/accounts/session/',REMOTE_ADDR='192.0.2.31',HTTP_X_FORWARDED_FOR='203.0.113.99')
        presence=PagePresence.objects.get(actor=self.user.username)
        self.assertEqual(presence.last_ip,'192.0.2.31')
        self.assertEqual(presence.route,'#/sports')

    def test_navigation_records_only_valid_route(self):
        response=self.client.post('/api/activity/navigation/',{'route':'#/betting-history','password':'DoNotStore'})
        self.assertEqual(response.status_code,200)
        log=ActivityLog.objects.filter(target_model='화면 이동').latest('pk')
        self.assertEqual(log.changes['route'],'#/betting-history')
        self.assertEqual(log.changes['screen'],'배팅 내역')
        from .models import PagePresence
        presence=PagePresence.objects.get(actor=self.user.username)
        self.assertEqual(presence.route,'#/betting-history')
        count=ActivityLog.objects.filter(target_model='화면 이동').count()
        self.client.post('/api/activity/navigation/',{'route':'#/sports','heartbeat':'1'})
        presence.refresh_from_db()
        self.assertEqual(presence.route,'#/sports')
        self.assertEqual(ActivityLog.objects.filter(target_model='화면 이동').count(),count)
        self.assertNotIn('DoNotStore',json.dumps(log.changes))
        self.assertEqual(self.client.post('/api/activity/navigation/',{'route':'https://example.com/?token=secret'}).status_code,400)

    def setUp(self):
        self.user=get_user_model().objects.create_user(username='audit_member',password='NeverLogPassword123!')
        self.wallet=Wallet.objects.create(member=self.user,available=50000)
        self.client.force_login(self.user)

    def test_f_updates_capture_each_account_before_and_after(self):
        token=context.set({'actor':self.user.username,'actor_kind':'member','request_id':uuid4()})
        try:
            Wallet.objects.filter(pk=self.wallet.pk,available=50000).update(available=F('available')-10000)
        finally: context.reset(token)
        log=ActivityLog.objects.filter(target_model='wallet.Wallet',action='update').latest('pk')
        self.assertEqual(log.actor,self.user.username)
        self.assertEqual(log.changes['available'],{'before':50000,'after':40000})
        other=get_user_model().objects.create_user(username='audit_other')
        second=Wallet.objects.create(member=other,available=100)
        Wallet.objects.filter(pk__in=[self.wallet.pk,second.pk]).update(points=F('points')+5)
        self.assertEqual(ActivityLog.objects.filter(target_model='wallet.Wallet',action='update',changes__points__after=5).count(),2)

    def test_requests_denials_and_admin_read_only(self):
        self.client.get('/api/sports/my-slips/')
        log=ActivityLog.objects.filter(action='request').latest('pk')
        self.assertEqual((log.actor,log.status_code,log.path),('audit_member',200,'/api/sports/my-slips/'))
        self.assertEqual(self.client.get('/admin/activity/activitylog/').status_code,302)
        admin=get_user_model().objects.create_superuser(username='audit_admin',password=None)
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/admin/activity/activitylog/').status_code,200)
        self.assertEqual(self.client.post(f'/admin/activity/activitylog/{log.pk}/change/',{}).status_code,403)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(csrf.post('/api/accounts/logout/').status_code,403)
        self.assertTrue(ActivityLog.objects.filter(action='request',path='/api/accounts/logout/',status_code=403).exists())

    def test_password_and_tokens_never_recorded(self):
        self.user.set_password('NewSecretPassword456!');self.user.save(update_fields=['password'])
        logs=list(ActivityLog.objects.values_list('changes',flat=True))
        encoded=json.dumps(logs)
        self.assertNotIn('NeverLogPassword123',encoded)
        self.assertNotIn('NewSecretPassword456',encoded)
        self.assertNotIn('pbkdf2_',encoded)
        self.assertTrue(ActivityLog.objects.filter(action='update',target_model='accounts.User').exists())
        client=Client();client.post('/api/accounts/login/',{'username':'unknown','password':'DO_NOT_LOG_THIS'})
        self.assertNotIn('DO_NOT_LOG_THIS',json.dumps(list(ActivityLog.objects.values_list('changes',flat=True))))

    def test_rollbacks_and_delete_and_relation(self):
        before=ActivityLog.objects.count()
        try:
            with transaction.atomic():
                Wallet.objects.filter(pk=self.wallet.pk).update(points=100)
                raise ValueError()
        except ValueError: pass
        self.assertEqual(ActivityLog.objects.count(),before)
        game=Game.objects.create(name='Audit game',slug='audit-game',category='ball');pk=game.pk;game.delete()
        self.assertTrue(ActivityLog.objects.filter(target_model='catalog.Game',target_id=str(pk),action='delete').exists())
        from django.contrib.auth.models import Group
        group=Group.objects.create(name='test');self.user.groups.add(group)
        self.assertTrue(ActivityLog.objects.filter(action='relation',target_model='accounts.User').exists())
