from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.urls import reverse
from uuid import uuid4
from wallet.models import Wallet, WalletEntry
from .models import DemoSlip,DemoLeg


class AdminHistoryTests(TestCase):
    def setUp(self):
        self.operator=get_user_model().objects.create_superuser('history-operator',password='qa-only-password')
        self.member=get_user_model().objects.create_user('history-member',nickname='회원별명')
        self.wallet=Wallet.objects.create(member=self.member,available=90000)
        self.slip=DemoSlip.objects.create(member=self.member,request_id=uuid4(),fingerprint='test',mode='multi',stake=10000,total_stake=10000,expected_return=20000,legs=[{}])
        DemoLeg.objects.create(slip=self.slip,position=0,selection={'eventId':'qa','home':'홈팀','away':'원정팀','name':'홈팀','market':'h2h','price':2,'startsAt':'2026-10-15T08:00:00Z','league':'테스트 리그'})
        self.url=reverse('admin:sportsfeed_demoslip_settle',args=[self.slip.pk])
        self.client.force_login(self.operator)

    def test_ticket_list_detail_korean_labels_and_selected_cells(self):
        response=self.client.get(reverse('admin:sportsfeed_demoslip_changelist'))
        for text in ('회원별명','홈팀','2.00','배팅금액','적중예상금액','배팅 취소','낙첨 처리','class="selected"'):
            self.assertContains(response,text)
        self.assertNotContains(response,'Total stake')
        detail=self.client.get(reverse('admin:sportsfeed_demoslip_change',args=[self.slip.pk]))
        self.assertContains(detail,'class="admin-ticket"');self.assertNotContains(detail,'class="form-row');self.assertNotContains(detail,'name="_save"')

    def test_cancel_refunds_once_and_disables_buttons(self):
        self.assertRedirects(self.client.post(self.url,{'result':'void'}),reverse('admin:sportsfeed_demoslip_changelist'))
        self.client.post(self.url,{'result':'void'})
        self.slip.refresh_from_db();self.wallet.refresh_from_db()
        self.assertEqual((self.slip.status,self.wallet.available),('void',100000))
        self.assertEqual(WalletEntry.objects.filter(kind='demo_settlement').count(),1)
        response=self.client.get(reverse('admin:sportsfeed_demoslip_change',args=[self.slip.pk]))
        self.assertNotContains(response,'value="void"')
        listing=self.client.get(reverse('admin:sportsfeed_demoslip_changelist'))
        self.assertNotContains(listing,f'data-slip-id="{self.slip.pk}"')
        archive=self.client.get(reverse('admin:sportsfeed_demoslip_changelist'),{'status__exact':'void'})
        self.assertContains(archive,f'data-slip-id="{self.slip.pk}"')

    def test_cancellation_returns_to_live_status_and_ignores_external_redirect(self):
        self.assertContains(self.client.get(reverse('admin:sportsfeed_demoslip_changelist')),'data-confirm-cancel="yes"')
        self.assertRedirects(self.client.post(self.url+'?next=/admin/betting-status/',{'result':'void'}),'/admin/betting-status/')
        self.assertRedirects(self.client.post(self.url+'?next=https://example.com/',{'result':'void'}),reverse('admin:sportsfeed_demoslip_changelist'))

    def test_lost_has_no_credit_and_repeated_cancel_cannot_reverse(self):
        self.client.post(self.url,{'result':'lost'});self.client.post(self.url,{'result':'void'})
        self.slip.refresh_from_db();self.wallet.refresh_from_db()
        self.assertEqual((self.slip.status,self.wallet.available),('lost',90000))

    def test_post_only_permissions_and_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code,405)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.operator)
        self.assertEqual(csrf.post(self.url,{'result':'void'}).status_code,403)
        staff=get_user_model().objects.create_user('readonly-history',is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_demoslip'))
        self.client.force_login(staff)
        self.assertNotContains(self.client.get(reverse('admin:sportsfeed_demoslip_changelist')),'value="void"')
        self.assertEqual(self.client.post(self.url,{'result':'void'}).status_code,403)
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,90000)

    def test_powerball_groups_multiple_picks(self):
        self.slip.source='powerball';self.slip.save()
        self.slip.results.update(selection={'eventId':'pb','away':'100회차','market':'general_parity','name':'홀','price':1.95})
        DemoLeg.objects.create(slip=self.slip,position=1,selection={'eventId':'pb','away':'100회차','market':'power_parity','name':'짝','price':1.95})
        response=self.client.get(reverse('admin:sportsfeed_demoslip_changelist'))
        self.assertContains(response,'100회차',count=1)
        self.assertContains(response,'class="selected">홀');self.assertContains(response,'class="selected">짝')
