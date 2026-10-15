from datetime import datetime,timedelta,timezone as tz
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase
from wallet.models import Wallet,MoneyRequest
from sportsfeed.models import DemoSlip,DemoLeg
from .admin_metrics import totals


class AdminMetricsTests(TestCase):
    def test_balance_link_lists_positive_member_balances_only(self):
        Wallet.objects.create(member=self.member,available=5000)
        Wallet.objects.create(member=self.other,available=0)
        Wallet.objects.create(member=self.admin,available=9000)
        response=self.client.get('/admin/wallet/wallet/?holders=yes')
        self.assertEqual(response.status_code,200)
        self.assertEqual([wallet.member_id for wallet in response.context['cl'].result_list],[self.member.pk])
        self.assertContains(self.client.get('/admin/'),'/admin/wallet/wallet/?holders=yes')

    def setUp(self):
        User=get_user_model()
        self.admin=User.objects.create_superuser(username='metrics_admin',password=None)
        self.member=User.objects.create_user(username='metrics_member',nickname='회원')
        self.other=User.objects.create_user(username='metrics_other')
        self.client.force_login(self.admin)

    def test_wallet_and_korean_approval_day(self):
        Wallet.objects.create(member=self.member,available=12345,reserved=5000)
        Wallet.objects.create(member=self.other,available=20000)
        Wallet.objects.create(member=self.admin,available=999999)
        now=datetime(2026,10,15,16,tzinfo=tz.utc) # Korea: October 16, 01:00.
        for kind,amount,status,processed in [('deposit',10000,'approved',now),('withdraw',3000,'approved',now),('deposit',50000,'pending',None),('deposit',9000,'approved',now-timedelta(hours=2))]:
            MoneyRequest.objects.create(member=self.member,kind=kind,amount=amount,status=status,processed_at=processed)
        with patch('config.admin_metrics.timezone.now',return_value=now):
            data=totals(self.admin)
        self.assertEqual({key:value['value'] for key,value in data.items()},{'balance':32345,'deposit':10000,'withdraw':3000,'pending_deposit':1,'pending_withdraw':0})
        self.assertEqual(totals(self.member),{})

    def test_pending_counters_links_and_processing(self):
        deposit=MoneyRequest.objects.create(member=self.member,kind='deposit',amount=10000)
        MoneyRequest.objects.create(member=self.other,kind='withdraw',amount=20000)
        MoneyRequest.objects.create(member=self.member,kind='withdraw',amount=30000,status='rejected')
        data=self.client.get('/admin/summary/').json()['totals']
        self.assertEqual(data['pending_deposit']['display'],'1건')
        self.assertEqual(data['pending_withdraw']['display'],'1건')
        response=self.client.get('/admin/')
        self.assertContains(response,'data-total="pending_deposit"')
        filtered=self.client.get('/admin/wallet/moneyrequest/?kind__exact=deposit&status__exact=pending')
        self.assertEqual(filtered.status_code,200)
        self.assertEqual(filtered.context['cl'].result_count,1)
        deposit.status='approved';deposit.save(update_fields=['status'])
        self.assertEqual(totals(self.admin)['pending_deposit']['value'],0)

    def test_all_members_pending_and_permissions(self):
        slips=[]
        for member,status in [(self.member,'pending'),(self.other,'pending'),(self.other,'won')]:
            slip=DemoSlip.objects.create(member=member,status=status,request_id=uuid4(),fingerprint='test',mode='multi',stake=10000,total_stake=10000,expected_return=20000)
            DemoLeg.objects.create(slip=slip,position=0,selection={'home':'Home','away':'Away','price':'2.0000','name':'Home'})
            slips.append(slip)
        response=self.client.get('/admin/betting-status/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total'],2)
        self.assertEqual({slip.pk for slip in response.context['page']},{slips[0].pk,slips[1].pk})
        self.assertContains(response,'Home');self.assertContains(response,'Away')
        self.assertContains(response,'class="admin-ticket"')
        self.assertNotContains(response,'상세 내역')
        self.assertContains(self.client.get('/admin/'),'data-total="balance"')
        self.assertEqual(self.client.get('/admin/summary/').status_code,200)
        self.member.is_staff=True;self.member.save()
        self.client.force_login(self.member)
        self.assertEqual(self.client.get('/admin/betting-status/').status_code,403)
        self.assertEqual(self.client.get('/admin/summary/').json()['totals'],{})
