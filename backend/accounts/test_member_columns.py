from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from wallet.models import Wallet,MoneyRequest
from sportsfeed.models import DemoSlip
from .member_columns import member_metrics,MemberColumns


class MemberColumnsTests(TestCase):
    def test_totals_and_admin_lists(self):
        User=get_user_model();admin=User.objects.create_superuser(username='columns_admin',password=None)
        referrer=User.objects.create_user(username='referrer')
        member=User.objects.create_user(username='columns_member',nickname='테스트',referrer=referrer,wallet_name='연습 지갑')
        Wallet.objects.create(member=member,available=5000,points=200)
        for kind,amount,status in [('deposit',10000,'approved'),('deposit',20000,'approved'),('withdraw',5000,'approved'),('deposit',90000,'pending')]:
            MoneyRequest.objects.create(member=member,kind=kind,amount=amount,status=status,processed_at=timezone.now() if status=='approved' else None)
        for status,credited in [('pending',0),('won',19500)]:
            DemoSlip.objects.create(member=member,request_id=uuid4(),fingerprint='test',mode='multi',stake=10000,total_stake=10000,expected_return=19500,status=status,credited_amount=credited,settled_at=timezone.now() if status=='won' else None)
        user=member_metrics(User.objects.all()).get(pk=member.pk)
        self.assertEqual((user.metric_money,user.metric_points,user.metric_deposit,user.metric_withdraw),(5000,200,30000,5000))
        self.assertEqual((user.metric_today_deposit,user.metric_today_withdraw,user.metric_bets,user.metric_profit),(30000,5000,20000,9500))
        self.client.force_login(admin)
        detail=self.client.get(f'/admin/accounts/user/{member.pk}/change/')
        self.assertContains(detail,'class="member-financial-table"')
        self.assertContains(detail,'30,000 / 5,000')
        self.assertContains(detail,'9,500')
        self.assertContains(detail,'referrer')
        self.assertIn('member_financial_summary',list(detail.context['adminform'])[0].fields)
        for url in ['/admin/accounts/user/','/admin/wallet/wallet/?holders=yes']:
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'연습 지갑')
            self.assertContains(response,'30,000 / 5,000')
            self.assertEqual(tuple(field for field in response.context['cl'].list_display if field!='action_checkbox'),MemberColumns.member_columns)
