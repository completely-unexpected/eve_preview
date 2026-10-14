from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings


@override_settings(DEBUG=True)
class AccountAPITests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.password = "River!Orbit-2026-test"

    def post(self, action, data=None):
        token = self.client.get("/api/accounts/session/").json()["csrfToken"]
        return self.client.post("/api/accounts/" + action + "/", data or {}, HTTP_X_CSRFTOKEN=token)

    def signup_data(self, **changes):
        data = {"username": "test_member", "nickname": "테스트 회원", "password1": self.password, "password2": self.password}
        data.update(changes)
        return data

    def test_signup_hashes_password_and_starts_session(self):
        response = self.post("signup", self.signup_data())
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="test_member")
        self.assertNotEqual(user.password, self.password)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.nickname, "테스트 회원")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(self.client.get("/api/accounts/session/").json()["authenticated"])

    def test_mismatched_password_does_not_create_user(self):
        response = self.post("signup", self.signup_data(password2="Something!Different"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("password2", response.json()["errors"])
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_weak_password_rejected(self):
        self.assertEqual(self.post("signup", self.signup_data(password1="123", password2="123")).status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_nickname_required(self):
        response = self.post("signup", self.signup_data(nickname=""))
        self.assertEqual(response.status_code, 400)
        self.assertIn("nickname", response.json()["errors"])

    def test_duplicate_username_rejected(self):
        get_user_model().objects.create_user(username="test_member", password=self.password)
        self.assertEqual(self.post("signup", self.signup_data()).status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_authenticated_signup_rejected(self):
        self.post("signup", self.signup_data())
        self.assertEqual(self.post("signup", self.signup_data(username="second_member")).status_code, 409)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_login_and_logout(self):
        get_user_model().objects.create_user(username="test_member", nickname="회원", password=self.password)
        self.assertEqual(self.post("login", {"username": "test_member", "password": self.password}).status_code, 200)
        self.assertTrue(self.client.get("/api/accounts/session/").json()["authenticated"])
        self.assertEqual(self.post("logout").status_code, 200)
        self.assertFalse(self.client.get("/api/accounts/session/").json()["authenticated"])

    def test_wrong_password_and_inactive_user_rejected(self):
        user = get_user_model().objects.create_user(username="test_member", password=self.password)
        self.assertEqual(self.post("login", {"username": user.username, "password": "wrong"}).status_code, 400)
        user.is_active = False
        user.save()
        self.assertEqual(self.post("login", {"username": user.username, "password": self.password}).status_code, 400)
        self.assertFalse(self.client.get("/api/accounts/session/").json()["authenticated"])

    def test_post_without_csrf_is_rejected(self):
        for action in ("signup", "login", "logout"):
            response = self.client.post("/api/accounts/" + action + "/", self.signup_data())
            self.assertEqual(response.status_code, 403)
            self.assertFalse(response.json()["ok"])

    def test_external_origin_is_rejected(self):
        token = self.client.get("/api/accounts/session/").json()["csrfToken"]
        response = self.client.post("/api/accounts/signup/", self.signup_data(), HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://external.example")
        self.assertEqual(response.status_code, 403)

    def test_mutating_endpoints_reject_get(self):
        for action in ("signup", "login", "logout"):
            self.assertEqual(self.client.get("/api/accounts/" + action + "/").status_code, 405)

    def test_session_no_cache_and_no_password_fields(self):
        self.post("signup", self.signup_data())
        response = self.client.get("/api/accounts/session/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("password", response.json()["user"])

    def test_home_and_frontend_assets_served(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        for asset in ("app.js", "auth.js", "styles.css", "functionality.css", "auth.css", "assets/hero-sports.svg"):
            response = self.client.get("/" + asset)
            self.assertEqual(response.status_code, 200)
            response.close()
