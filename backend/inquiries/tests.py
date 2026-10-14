from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from .models import Inquiry

class InquiryTests(TestCase):
    def setUp(self):
        self.User=get_user_model()
        self.member=self.User.objects.create_user(username="member", password="Orbit!2026-Inquiry")
        self.other=self.User.objects.create_user(username="other")
        self.inquiry=Inquiry.objects.create(member=self.member,title="내 문의",body="내용")
        self.private=Inquiry.objects.create(member=self.other,title="다른 회원 문의",body="비밀")
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.member)

    def post(self,data):
        token=self.client.get('/api/accounts/session/').json()['csrfToken']
        return self.client.post('/api/inquiries/',data,HTTP_X_CSRFTOKEN=token)

    def test_only_own_list_and_detail(self):
        response=self.client.get('/api/inquiries/')
        self.assertEqual([n['id'] for n in response.json()['items']],[self.inquiry.pk])
        self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(self.client.get(f'/api/inquiries/{self.inquiry.pk}/').status_code,200)
        self.assertEqual(self.client.get(f'/api/inquiries/{self.private.pk}/').status_code,404)
        self.assertEqual(self.client.get('/api/inquiries/999999/').status_code,404)

    def test_owner_and_answer_cannot_be_forged(self):
        response=self.post({'title':' 신규 ', 'body':' 새 내용 ', 'member':self.other.pk,'answer':'위조','answered_by':self.other.pk})
        self.assertEqual(response.status_code,201)
        obj=Inquiry.objects.get(pk=response.json()['inquiry']['id'])
        self.assertEqual(obj.member,self.member)
        self.assertEqual(obj.title,'신규')
        self.assertEqual(obj.body,'새 내용')
        self.assertEqual(obj.answer,'')
        self.assertIsNone(obj.answered_by)

    def test_validation_and_csrf(self):
        for data in ({'title':' ', 'body':'내용'},{'title':'제목','body':' '},{'title':'가'*201,'body':'내용'},{'title':'제목','body':'가'*10001}):
            self.assertEqual(self.post(data).status_code,400)
        self.assertEqual(self.client.post('/api/inquiries/',{'title':'제목','body':'내용'}).status_code,403)
        self.assertEqual(Inquiry.objects.count(),2)

    def test_anonymous_and_suspended_blocked(self):
        anonymous=Client()
        for path in ('/api/inquiries/',f'/api/inquiries/{self.inquiry.pk}/'):
            self.assertEqual(anonymous.get(path).status_code,401)
        self.member.account_status=self.User.Status.SUSPENDED
        self.member.save()
        self.assertEqual(self.client.get('/api/inquiries/').status_code,401)

    def test_pagination_and_detail_read_only(self):
        Inquiry.objects.bulk_create([Inquiry(member=self.member,title=str(i),body='내용') for i in range(22)])
        self.assertEqual(len(self.client.get('/api/inquiries/').json()['items']),20)
        self.assertEqual(len(self.client.get('/api/inquiries/?page=2').json()['items']),3)
        token=self.client.get('/api/accounts/session/').json()['csrfToken']
        self.assertEqual(self.client.post(f'/api/inquiries/{self.inquiry.pk}/',{},HTTP_X_CSRFTOKEN=token).status_code,405)

    def test_admin_answer_and_member_permissions(self):
        self.assertEqual(self.client.get('/admin/inquiries/inquiry/').status_code,302)
        operator=self.User.objects.create_superuser(username='operator',password='Orbit!2026-Admin')
        admin=Client()
        admin.force_login(operator)
        self.assertEqual(admin.get('/admin/inquiries/inquiry/').status_code,200)
        response=admin.post(f'/admin/inquiries/inquiry/{self.inquiry.pk}/change/',{'answer':' 답변 내용 ', '_save':'저장', 'member':self.other.pk,'title':'위조'})
        self.assertEqual(response.status_code,302)
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.member,self.member)
        self.assertEqual(self.inquiry.title,'내 문의')
        self.assertEqual(self.inquiry.answer,'답변 내용')
        self.assertEqual(self.inquiry.answered_by,operator)
        self.assertIsNotNone(self.inquiry.answered_at)
        self.assertEqual(self.client.get(f'/api/inquiries/{self.inquiry.pk}/').json()['inquiry']['answer'],'답변 내용')
        admin.post(f'/admin/inquiries/inquiry/{self.inquiry.pk}/change/',{'answer':'','_save':'저장'})
        self.inquiry.refresh_from_db()
        self.assertIsNone(self.inquiry.answered_at)
        self.assertIsNone(self.inquiry.answered_by)
