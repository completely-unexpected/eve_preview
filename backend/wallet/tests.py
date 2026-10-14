from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase,Client
from django.urls import reverse
from wallet.models import Wallet,MoneyRequest,WalletEntry,PointGrant,PointConversion
from wallet.services import request_money,decide,grant_points,convert_points

class WalletTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.member=User.objects.create_user(username='member',password='Orbit!2026-Member')
        self.other=User.objects.create_user(username='other')
        self.admin=User.objects.create_superuser(username='operator',password='Orbit!2026-Admin')
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.member)
    def post(self,path,data):
        csrf=self.client.get('/api/accounts/session/').json()['csrfToken']
        return self.client.post('/api/wallet/'+path,data,HTTP_X_CSRFTOKEN=csrf)
    def wallet(self):return Wallet.objects.get(member=self.member)
    def test_deposit_approval_once_and_rejection(self):
        response=self.post('apply/',{'kind':'deposit','amount':'1000'})
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.wallet().available,0)
        record=MoneyRequest.objects.get(pk=response.json()['request']['id'])
        decide(record.pk,self.admin,True)
        self.assertEqual(self.wallet().available,1000)
        with self.assertRaises(ValidationError):decide(record.pk,self.admin,True)
        self.assertEqual(self.wallet().available,1000)
        rejected=request_money(self.member,'deposit',200)
        decide(rejected.pk,self.admin,False)
        self.assertEqual(self.wallet().available,1000)
        self.assertEqual(WalletEntry.objects.filter(kind='deposit_approved').count(),1)
    def test_withdraw_reservation_approval_and_rejection(self):
        deposit=request_money(self.member,'deposit',1000);decide(deposit.pk,self.admin,True)
        first=request_money(self.member,'withdraw',700)
        self.assertEqual((self.wallet().available,self.wallet().reserved),(300,700))
        with self.assertRaises(ValidationError):request_money(self.member,'withdraw',301)
        decide(first.pk,self.admin,False)
        self.assertEqual((self.wallet().available,self.wallet().reserved),(1000,0))
        second=request_money(self.member,'withdraw',600)
        decide(second.pk,self.admin,True)
        self.assertEqual((self.wallet().available,self.wallet().reserved),(400,0))
        with self.assertRaises(ValidationError):decide(second.pk,self.admin,False)
        self.assertEqual(Wallet.objects.get(member=self.member).available,400)
    def test_grant_and_convert_exact_ratio_and_history(self):
        grant_points(self.member,700,'테스트 지급',self.admin)
        self.assertEqual(self.wallet().points,700)
        self.assertEqual(self.post('convert/',{'points':'300'}).status_code,201)
        self.assertEqual((self.wallet().available,self.wallet().points),(300,400))
        self.assertEqual(PointConversion.objects.get().points,300)
        self.assertEqual(self.client.get('/api/wallet/').json()['grants'][0]['reason'],'테스트 지급')
        self.assertEqual(self.post('convert/',{'points':'401'}).status_code,400)
        self.assertEqual((self.wallet().available,self.wallet().points),(300,400))
    def test_validation_permissions_and_isolation(self):
        for amount in ('0','-1','1.2','abc','1000000000001'):
            self.assertEqual(self.post('apply/',{'kind':'deposit','amount':amount}).status_code,400)
            self.assertEqual(self.post('convert/',{'points':amount}).status_code,400)
        self.assertEqual(self.post('apply/',{'kind':'other','amount':'1'}).status_code,400)
        self.assertEqual(MoneyRequest.objects.count(),0)
        request_money(self.other,'deposit',99)
        response=self.client.get('/api/wallet/')
        self.assertEqual(response.json()['requests'],[])
        self.assertIn('no-store',response['Cache-Control'])
        other=Client()
        self.assertEqual(other.get('/api/wallet/').status_code,401)
        self.assertEqual(other.post('/api/wallet/apply/',{'kind':'deposit','amount':'5'}).status_code,401)
        self.assertEqual(self.client.post('/api/wallet/convert/',{'points':'1'}).status_code,403)
        with self.assertRaises(ValidationError):grant_points(self.member,100,'no permission',self.member)
        with self.assertRaises(ValidationError):decide(MoneyRequest.objects.first().pk,self.member,True)
    def test_admin_actions_and_point_grant_form(self):
        adminclient=Client();adminclient.force_login(self.admin)
        grant_url='/admin/wallet/pointgrant/add/'
        response=adminclient.post(grant_url,{'member':self.member.pk,'amount':500,'reason':'관리자 지급','_save':'저장'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.wallet().points,500)
        self.assertEqual(PointGrant.objects.count(),1)
        deposit=request_money(self.member,'deposit',250)
        response=adminclient.post('/admin/wallet/moneyrequest/',{'action':'approve_selected','_selected_action':[deposit.pk],'index':0})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.wallet().available,250)
        adminclient.post('/admin/wallet/moneyrequest/',{'action':'approve_selected','_selected_action':[deposit.pk],'index':0})
        self.assertEqual(self.wallet().available,250)
        self.assertEqual(WalletEntry.objects.filter(kind='deposit_approved').count(),1)
