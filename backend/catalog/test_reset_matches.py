from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from sportsfeed.models import FeedSnapshot,OddsPortalSnapshot,HarvesterSnapshot,DemoSlip
from wallet.models import Wallet
from .reset_matches import clear_matches


@patch('catalog.reset_matches.set_paused')
@patch('catalog.reset_matches.is_paused',return_value=False)
class ResetMatchesTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('match-reset-admin')
        self.member=get_user_model().objects.create_user('match-reset-member')
        self.wallet=Wallet.objects.create(member=self.member,available=12345)
        self.slip=DemoSlip.objects.create(member=self.member,request_id=uuid4(),fingerprint='qa',mode='multi',stake=100,total_stake=100,expected_return=200)
        for model in (FeedSnapshot,OddsPortalSnapshot,HarvesterSnapshot): model.objects.create(payload={'items':[{'id':'active','status':'upcoming'},{'id':'done','status':'finished'}]})
        self.client.force_login(self.admin)
        self.url=reverse('admin:catalog_game_reset_matches')

    def test_clears_active_matches_only(self,paused,set_paused):
        self.assertEqual(clear_matches(self.admin),3)
        for model in (FeedSnapshot,OddsPortalSnapshot,HarvesterSnapshot): self.assertEqual([row['id'] for row in model.objects.get().payload['items']],['done'])
        self.assertTrue(DemoSlip.objects.filter(pk=self.slip.pk).exists())
        self.wallet.refresh_from_db();self.assertEqual(self.wallet.available,12345)
        self.assertTrue(get_user_model().objects.filter(pk=self.member.pk).exists())
        set_paused.assert_called_once_with(True)

    def test_requires_confirmation_and_permission(self,paused,set_paused):
        self.assertContains(self.client.get(self.url),'경기 전체 삭제 실행')
        self.client.post(self.url,{})
        self.assertEqual(len(FeedSnapshot.objects.get().payload['items']),2)
        set_paused.assert_not_called()
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.url,{'confirm':'yes'}).status_code,302)
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(self.url,{'confirm':'yes'}),reverse('admin:catalog_game_odds'))

    def test_busy_import_prevents_partial_clear_and_restores_pause(self,paused,set_paused):
        FeedSnapshot.objects.update(syncing=True)
        with self.assertRaises(ValidationError): clear_matches(self.admin)
        self.assertEqual(len(OddsPortalSnapshot.objects.get().payload['items']),2)
        self.assertEqual(set_paused.call_args_list[-1].args,(False,))
