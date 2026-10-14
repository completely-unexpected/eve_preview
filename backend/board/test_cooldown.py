from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone
from .models import Post
class PostingCooldownTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='poster')
        self.client.force_login(self.user)
    def post(self,**changes):
        data={'title':'게시글','body':'내용'};data.update(changes)
        return self.client.post('/api/board/',data)
    def test_immediate_duplicate_rejected_without_creating_post(self):
        self.assertEqual(self.post().status_code,201)
        response=self.post()
        self.assertEqual(response.status_code,429)
        self.assertGreater(response.json()['retryAfter'],0)
        self.assertLessEqual(response.json()['retryAfter'],30)
        self.assertEqual(response['Retry-After'],str(response.json()['retryAfter']))
        self.assertEqual(Post.objects.count(),1)
    def test_after_thirty_seconds_allowed(self):
        now=timezone.now()
        with patch('board.views.timezone.now',return_value=now):self.assertEqual(self.post().status_code,201)
        with patch('board.views.timezone.now',return_value=now+timedelta(seconds=30)):self.assertEqual(self.post().status_code,201)
    def test_other_session_blocked_and_other_member_independent(self):
        self.post()
        second=Client();second.force_login(self.user)
        self.assertEqual(second.post('/api/board/',{'title':'글','body':'내용'}).status_code,429)
        other=get_user_model().objects.create_user(username='other');second.force_login(other)
        self.assertEqual(second.post('/api/board/',{'title':'글','body':'내용'}).status_code,201)
    def test_bad_form_does_not_start_cooldown(self):
        self.assertEqual(self.post(title=' ').status_code,400)
        self.user.refresh_from_db();self.assertIsNone(self.user.board_last_post_at)
        self.assertEqual(self.post().status_code,201)
    def test_failed_save_rolls_back_reservation(self):
        with patch('board.views.Post.objects.create',side_effect=RuntimeError('simulated save failure')):
            with self.assertRaises(RuntimeError):self.post()
        self.user.refresh_from_db();self.assertIsNone(self.user.board_last_post_at)
        self.assertEqual(self.post().status_code,201)
