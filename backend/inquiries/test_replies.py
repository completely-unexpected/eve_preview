from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone
from .models import Inquiry

class ReplyAlertTests(TestCase):
    def setUp(self):
        self.member=get_user_model().objects.create_user(username='member')
        self.other=get_user_model().objects.create_user(username='other')
        self.reply=Inquiry.objects.create(member=self.member,title='문의',body='내용',answer='답변',answered_at=timezone.now())
        self.private=Inquiry.objects.create(member=self.other,title='다른 문의',body='내용',answer='비밀 답변',answered_at=timezone.now())
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.member)
    def read(self,pk=None,answered=None):
        token=self.client.get('/api/accounts/session/').json()['csrfToken']
        return self.client.post(f'/api/inquiries/{pk or self.reply.pk}/read/',{'answered_at':answered if answered is not None else self.reply.answered_at.isoformat()},HTTP_X_CSRFTOKEN=token)
    def test_own_unread_count_and_explicit_read(self):
        self.assertEqual(self.client.get('/api/accounts/session/').json()['unreadReplies'],1)
        self.assertTrue(self.client.get('/api/inquiries/').json()['items'][0]['unread'])
        self.client.get(f'/api/inquiries/{self.reply.pk}/')
        self.assertEqual(self.client.get('/api/accounts/session/').json()['unreadReplies'],1)
        self.assertEqual(self.read().status_code,200)
        self.assertEqual(self.client.get('/api/accounts/session/').json()['unreadReplies'],0)
        self.assertEqual(self.read().status_code,200)
    def test_other_member_cannot_read(self):
        self.assertEqual(self.read(self.private.pk).status_code,404)
        self.private.refresh_from_db()
        self.assertIsNone(self.private.answer_read_at)
    def test_stale_answer_stays_unread(self):
        old=self.reply.answered_at.isoformat()
        self.reply.answered_at=timezone.now()
        self.reply.answer='새 답변'
        self.reply.save()
        self.assertEqual(self.read(answered=old).status_code,200)
        self.assertEqual(self.client.get('/api/accounts/session/').json()['unreadReplies'],1)
    def test_admin_edit_renotifies_and_delete_clears(self):
        self.read()
        operator=get_user_model().objects.create_superuser(username='operator',password='Orbit!2026-Reply')
        admin=Client();admin.force_login(operator)
        admin.post(f'/admin/inquiries/inquiry/{self.reply.pk}/change/',{'answer':'수정 답변','_save':'저장'})
        self.assertEqual(self.client.get('/api/accounts/session/').json()['unreadReplies'],1)
        admin.post(f'/admin/inquiries/inquiry/{self.reply.pk}/change/',{'answer':'','_save':'저장'})
        self.assertEqual(self.client.get('/api/accounts/session/').json()['unreadReplies'],0)
    def test_csrf_method_and_anonymous(self):
        url=f'/api/inquiries/{self.reply.pk}/read/'
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url,{}).status_code,403)
        self.assertEqual(Client().post(url,{}).status_code,401)
        self.assertEqual(Client().get('/api/accounts/session/').json()['unreadReplies'],0)
