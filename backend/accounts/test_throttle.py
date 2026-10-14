from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone
from accounts.models import LoginThrottle

class LoginThrottleTests(TestCase):
    def setUp(self):
        self.password='Orbit!2026-Throttle'
        self.user=get_user_model().objects.create_user(username='limited_member',password=self.password)
        self.client=Client(enforce_csrf_checks=True)
    def login(self,password='wrong',username='limited_member',ip='127.0.0.1',**headers):
        token=self.client.get('/api/accounts/session/').json()['csrfToken']
        return self.client.post('/api/accounts/login/',{'username':username,'password':password},HTTP_X_CSRFTOKEN=token,REMOTE_ADDR=ip,**headers)
    def test_fifth_failure_and_correct_password_blocked(self):
        for _ in range(4):self.assertEqual(self.login().status_code,400)
        response=self.login()
        self.assertEqual(response.status_code,429)
        self.assertGreater(int(response['Retry-After']),0)
        self.assertLessEqual(response.json()['retryAfter'],300)
        self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(self.login(self.password).status_code,429)
        self.assertFalse(self.client.get('/api/accounts/session/').json()['authenticated'])
    def test_expiration_allows_login_without_sleep(self):
        for _ in range(5):self.login()
        future=timezone.now()+timedelta(minutes=6)
        with patch('accounts.throttle.timezone.now',return_value=future):
            self.assertEqual(self.login(self.password).status_code,200)
        self.assertEqual(LoginThrottle.objects.count(),0)
    def test_success_resets_failures(self):
        for _ in range(4):self.login()
        self.assertEqual(self.login(self.password).status_code,200)
        self.assertEqual(LoginThrottle.objects.count(),0)
        self.assertEqual(self.login().status_code,400)
    def test_failure_window_resets(self):
        for _ in range(4):self.login()
        with patch('accounts.throttle.timezone.now',return_value=timezone.now()+timedelta(minutes=6)):
            self.assertEqual(self.login().status_code,400)
        self.assertEqual(LoginThrottle.objects.get().failures,1)
    def test_other_ip_and_username_are_independent(self):
        for _ in range(5):self.login()
        self.assertEqual(self.login(self.password,ip='192.0.2.2').status_code,200)
        self.assertEqual(self.login(username='different').status_code,400)
    def test_forwarded_headers_do_not_bypass(self):
        for _ in range(5):self.login()
        self.assertEqual(self.login(self.password,HTTP_X_FORWARDED_FOR='192.0.2.9').status_code,429)
    def test_unknown_username_has_same_limit(self):
        for _ in range(4):self.assertEqual(self.login(username='missing').status_code,400)
        self.assertEqual(self.login(username='missing').status_code,429)
    def test_pending_correct_password_is_not_counted(self):
        self.user.account_status=get_user_model().Status.PENDING
        self.user.save()
        self.login()
        for _ in range(6):self.assertEqual(self.login(self.password).status_code,403)
        self.assertEqual(LoginThrottle.objects.count(),0)
    def test_csrf_rejection_does_not_count(self):
        self.assertEqual(self.client.post('/api/accounts/login/',{'username':self.user.username,'password':'wrong'}).status_code,403)
        self.assertEqual(LoginThrottle.objects.count(),0)
