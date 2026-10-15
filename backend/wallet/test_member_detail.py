from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from .models import Wallet
from activity.models import PagePresence


class MemberDetailTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='detail_admin',password=None)
        self.member=get_user_model().objects.create_user(username='detail_member')
        self.wallet=Wallet.objects.create(member=self.member,available=10000)
        self.url=f'/admin/wallet/wallet/{self.wallet.pk}/member/'

    def test_detail_link_fields_and_safe_edits(self):
        self.client.force_login(self.member)
        self.client.post('/api/activity/navigation/',{'route':'#/betting-history'},REMOTE_ADDR='192.0.2.15',HTTP_X_FORWARDED_FOR='203.0.113.20')
        self.assertEqual(PagePresence.objects.get(actor=self.member.username).last_ip,'192.0.2.15')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/admin/wallet/wallet/?holders=yes'),f'/admin/accounts/user/{self.member.pk}/change/')
        account_response=self.client.get(f'/admin/accounts/user/{self.member.pk}/change/')
        self.assertEqual(account_response.status_code,200)
        sections=list(account_response.context['adminform'])
        self.assertEqual(sections[0].name,'개인정보')
        self.assertContains(account_response,'192.0.2.15')
        self.assertContains(account_response,'배팅 내역')
        response=self.client.get(self.url)
        for value in ('이름','전화번호','지갑번호','접속 IP','현재 이용 위치','비고','배팅 내역','192.0.2.15'):
            self.assertContains(response,value)
        response=self.client.post(self.url,{'legal_name':'테스트 이름','phone_number':'010-1234-5678','wallet_number':'W-001','admin_notes':'확인 메모','available':'999999','is_superuser':'1'})
        self.assertEqual(response.status_code,302)
        self.member.refresh_from_db();self.wallet.refresh_from_db()
        self.assertEqual(self.member.legal_name,'테스트 이름')
        self.assertEqual(self.member.admin_notes,'확인 메모')
        self.assertFalse(self.member.is_superuser)
        self.assertEqual(self.wallet.available,10000)

    def test_permissions(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code,302)
        viewer=get_user_model().objects.create_user(username='detail_viewer',is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_wallet'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code,403)
        viewer.user_permissions.add(Permission.objects.get(codename='view_user'))
        self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(self.client.post(self.url,{}).status_code,403)
