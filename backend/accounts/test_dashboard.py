from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from inquiries.models import Inquiry

class DashboardTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.operator=User.objects.create_superuser(username='operator',password='Orbit!2026-Dashboard')
        self.member=User.objects.create_user(username='member')
        self.pending=User.objects.create_user(username='pending',account_status='pending')
        User.objects.create_user(username='suspended',account_status='suspended')
        Inquiry.objects.create(member=self.member,title='대기',body='내용')
        Inquiry.objects.create(member=self.member,title='완료',body='내용',answer='답변')
    def test_anonymous_regular_and_inactive_staff_cannot_read(self):
        self.assertEqual(self.client.get('/admin/overview/').status_code,302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get('/admin/overview/').status_code,302)
        self.operator.is_active=False
        # Status drives is_active, so mark the DB directly for this access test.
        get_user_model().objects.filter(pk=self.operator.pk).update(is_active=False)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get('/admin/overview/').status_code,302)
    def test_counts_links_and_admin_home(self):
        self.client.force_login(self.operator)
        response=self.client.get('/admin/overview/')
        self.assertEqual(response.status_code,200)
        self.assertIn('no-cache',response['Cache-Control'])
        counts={card['label']:card['count'] for card in response.context['cards']}
        self.assertEqual(counts,{'전체 회원':4,'승인 대기':1,'이용 정지':1,'전체 문의':2,'답변 대기 문의':1})
        for card in response.context['cards']:
            self.assertEqual(self.client.get(card['url']).status_code,200)
        self.assertContains(self.client.get('/admin/'),'관리자 현황 보기')
    def test_permissionless_staff_see_no_counts(self):
        staff=get_user_model().objects.create_user(username='staff',is_staff=True)
        self.client.force_login(staff)
        response=self.client.get('/admin/overview/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['cards'],[])
        staff.user_permissions.add(Permission.objects.get(content_type__app_label='inquiries',codename='view_inquiry'))
        response=self.client.get('/admin/overview/')
        self.assertEqual([card['label'] for card in response.context['cards']],['전체 문의','답변 대기 문의'])
    def test_counts_update_and_post_rejected(self):
        self.client.force_login(self.operator)
        self.pending.account_status='approved'
        self.pending.save()
        Inquiry.objects.filter(answer='').update(answer='답변 완료')
        response=self.client.get('/admin/overview/')
        counts={card['label']:card['count'] for card in response.context['cards']}
        self.assertEqual(counts['승인 대기'],0)
        self.assertEqual(counts['답변 대기 문의'],0)
        self.assertEqual(self.client.post('/admin/overview/').status_code,405)
