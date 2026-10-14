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

    def test_signup_hashes_password_and_waits_for_approval(self):
        response = self.post("signup", self.signup_data())
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="test_member")
        self.assertNotEqual(user.password, self.password)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.nickname, "테스트 회원")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_active)
        self.assertEqual(user.account_status, get_user_model().Status.PENDING)
        self.assertTrue(response.json()["approvalRequired"])
        self.assertFalse(self.client.get("/api/accounts/session/").json()["authenticated"])

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
        user = get_user_model().objects.create_user(username="test_member", password=self.password)
        self.client.force_login(user)
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
        user.account_status = get_user_model().Status.SUSPENDED
        user.save()
        self.assertEqual(self.post("login", {"username": user.username, "password": self.password}).status_code, 403)
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
        user = get_user_model().objects.create_user(username="test_member", password=self.password)
        self.client.force_login(user)
        response = self.client.get("/api/accounts/session/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("password", response.json()["user"])

    def test_home_and_frontend_assets_served(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        for asset in ("app.js", "auth.js", "styles.css", "functionality.css", "auth.css", "assets/hero-sports.svg"):
            response = self.client.get("/" + asset)
            self.assertEqual(response.status_code, 200)
            response.close()


class MemberApprovalTests(TestCase):
    def setUp(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        self.User = get_user_model()
        self.password = "River!Orbit-2026-test"
        self.member = self.User.objects.create_user(username="pending_member", password=self.password, account_status=self.User.Status.PENDING)
        self.operator = self.User.objects.create_superuser(username="operator", password=self.password)
        self.admin = site._registry[self.User]
        self.request = RequestFactory().post("/admin/accounts/user/")
        self.request.user = self.operator
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)

    def login_member(self):
        return self.client.post("/api/accounts/login/", {"username": self.member.username, "password": self.password})

    def selected(self):
        return self.User.objects.filter(pk=self.member.pk)

    def test_pending_login_blocked_with_correct_credentials(self):
        response = self.login_member()
        self.assertEqual(response.status_code, 403)
        self.assertIn("승인", response.json()["message"])
        self.assertFalse(self.client.get("/api/accounts/session/").json()["authenticated"])

    def test_pending_status_not_revealed_for_wrong_password(self):
        response = self.client.post("/api/accounts/login/", {"username": self.member.username, "password": "wrong"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("message", response.json())

    def test_approval_enables_login_and_records_audit(self):
        from django.contrib.admin.models import LogEntry
        self.admin.approve_members(self.request, self.selected())
        self.member.refresh_from_db()
        self.assertEqual(self.member.account_status, self.User.Status.APPROVED)
        self.assertTrue(self.member.is_active)
        self.assertEqual(self.login_member().status_code, 200)
        self.assertTrue(LogEntry.objects.filter(user=self.operator, object_id=str(self.member.pk), change_message="가입 승인").exists())

    def test_suspension_blocks_existing_session_and_login(self):
        self.admin.approve_members(self.request, self.selected())
        self.login_member()
        self.admin.suspend_members(self.request, self.selected())
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertFalse(self.client.get("/api/accounts/session/").json()["authenticated"])
        response = self.login_member()
        self.assertEqual(response.status_code, 403)
        self.assertIn("정지", response.json()["message"])

    def test_restore_allows_login_again(self):
        self.admin.approve_members(self.request, self.selected())
        self.admin.suspend_members(self.request, self.selected())
        self.admin.restore_members(self.request, self.selected())
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)
        self.assertEqual(self.login_member().status_code, 200)

    def test_old_session_does_not_revive_after_suspension_and_restore(self):
        self.admin.approve_members(self.request, self.selected())
        self.login_member()
        self.admin.suspend_members(self.request, self.selected())
        self.admin.restore_members(self.request, self.selected())
        self.assertFalse(self.client.get("/api/accounts/session/").json()["authenticated"])
        self.assertEqual(self.login_member().status_code, 200)

    def test_existing_active_members_keep_original_session_hash(self):
        from django.contrib.auth.models import AbstractUser
        self.assertEqual(self.operator.get_session_auth_hash(), AbstractUser._get_session_auth_hash(self.operator))

    def test_actions_protect_staff_and_superuser(self):
        staff = self.User.objects.create_user(username="staff", is_staff=True)
        self.admin.suspend_members(self.request, self.User.objects.filter(pk__in=[self.operator.pk, staff.pk]))
        for user in (self.operator, staff):
            user.refresh_from_db()
            self.assertTrue(user.is_active)
            self.assertEqual(user.account_status, self.User.Status.APPROVED)

    def test_model_admin_validation_protects_admin_status(self):
        from django.core.exceptions import ValidationError
        self.operator.account_status = self.User.Status.SUSPENDED
        with self.assertRaises(ValidationError):
            self.operator.full_clean()

    def test_regular_member_cannot_manage_members(self):
        from django.core.exceptions import PermissionDenied
        self.member.account_status = self.User.Status.APPROVED
        self.member.save()
        self.request.user = self.member
        with self.assertRaises(PermissionDenied):
            self.admin.suspend_members(self.request, self.selected())
        self.client.force_login(self.member)
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 302)

    def test_approval_action_does_not_restore_suspended_members(self):
        self.member.account_status = self.User.Status.SUSPENDED
        self.member.save()
        self.admin.approve_members(self.request, self.selected())
        self.member.refresh_from_db()
        self.assertEqual(self.member.account_status, self.User.Status.SUSPENDED)
        self.assertFalse(self.member.is_active)

    def test_admin_status_filters_search_and_change_page(self):
        self.client.force_login(self.operator)
        for query in ("?account_status__exact=pending", "?q=pending_member"):
            self.assertEqual(self.client.get("/admin/accounts/user/" + query).status_code, 200)
        self.assertEqual(self.client.get(f"/admin/accounts/user/{self.member.pk}/change/").status_code, 200)

    def test_staff_created_pending_is_invalid(self):
        from django.core.exceptions import ValidationError
        user = self.User(username="new_staff", is_staff=True, account_status=self.User.Status.PENDING)
        with self.assertRaises(ValidationError):
            user.full_clean()


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.password = "River!Orbit-2026-test"
        self.member = get_user_model().objects.create_user(username="password_member", password=self.password)
        self.client.force_login(self.member)
        self.new_password = "Fresh!Mountain-2026-test"

    def post(self, action, data=None):
        token = self.client.get("/api/accounts/session/").json()["csrfToken"]
        return self.client.post("/api/accounts/" + action + "/", data or {}, HTTP_X_CSRFTOKEN=token)

    def change(self, **changes):
        data = {"old_password": self.password, "new_password1": self.new_password, "new_password2": self.new_password}
        data.update(changes)
        return self.post("password-change", data)

    def test_password_change_preserves_current_and_revokes_other_session(self):
        other = Client()
        other.force_login(self.member)
        response = self.change()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password(self.new_password))
        self.assertFalse(self.member.check_password(self.password))
        self.assertTrue(self.client.get("/api/accounts/session/").json()["authenticated"])
        self.assertFalse(other.get("/api/accounts/session/").json()["authenticated"])
        self.post("logout")
        self.assertEqual(self.post("login", {"username": self.member.username, "password": self.password}).status_code, 400)
        self.assertEqual(self.post("login", {"username": self.member.username, "password": self.new_password}).status_code, 200)

    def test_invalid_changes_do_not_change_password(self):
        for changes, field in [({"old_password": "wrong"}, "old_password"), ({"new_password2": "different"}, "new_password2"), ({"new_password1": "123", "new_password2": "123"}, "new_password2")]:
            response = self.change(**changes)
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.json()["errors"])
            self.member.refresh_from_db()
            self.assertTrue(self.member.check_password(self.password))

    def test_anonymous_and_suspended_cannot_change_password(self):
        anonymous = Client()
        self.assertEqual(anonymous.post("/api/accounts/password-change/", {}).status_code, 401)
        self.member.account_status = get_user_model().Status.SUSPENDED
        self.member.save()
        self.assertEqual(self.change().status_code, 401)

    def test_change_requires_post_and_csrf(self):
        self.assertEqual(self.client.get("/api/accounts/password-change/").status_code, 405)
        self.assertEqual(self.client.post("/api/accounts/password-change/", {}).status_code, 403)

    def test_change_after_suspension_and_restore_keeps_session(self):
        self.member.account_status = get_user_model().Status.SUSPENDED
        self.member.save()
        self.member.account_status = get_user_model().Status.APPROVED
        self.member.save()
        self.client.force_login(self.member)
        self.assertEqual(self.change().status_code, 200)
        self.assertTrue(self.client.get("/api/accounts/session/").json()["authenticated"])


class ProfileTests(TestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="profile_member", nickname="처음", password="Orbit!2026-Profile")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.member)

    def update(self, data):
        token = self.client.get("/api/accounts/session/").json()["csrfToken"]
        return self.client.post("/api/accounts/profile/", data, HTTP_X_CSRFTOKEN=token)

    def test_nickname_persists_without_changing_other_fields(self):
        other = get_user_model().objects.create_user(username="other", nickname="다른 회원")
        password_hash = self.member.password
        response = self.update({"nickname": " 새 닉네임 ", "username": "hacked", "is_staff": "true", "account_status": "suspended", "id": other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["nickname"], "새 닉네임")
        self.assertEqual(self.client.get("/api/accounts/session/").json()["user"]["nickname"], "새 닉네임")
        self.member.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.member.username, "profile_member")
        self.assertFalse(self.member.is_staff)
        self.assertTrue(self.member.is_active)
        self.assertEqual(self.member.password, password_hash)
        self.assertEqual(other.nickname, "다른 회원")

    def test_invalid_nickname_keeps_original(self):
        for data in ({}, {"nickname": "   "}, {"nickname": "가" * 31}):
            response = self.update(data)
            self.assertEqual(response.status_code, 400)
            self.assertIn("nickname", response.json()["errors"])
        self.member.refresh_from_db()
        self.assertEqual(self.member.nickname, "처음")
        self.assertEqual(self.update({"nickname": "가" * 30}).status_code, 200)

    def test_anonymous_and_suspended_rejected(self):
        self.assertEqual(Client().post("/api/accounts/profile/", {"nickname": "변경"}).status_code, 401)
        self.member.account_status = get_user_model().Status.SUSPENDED
        self.member.save()
        self.assertEqual(self.update({"nickname": "변경"}).status_code, 401)

    def test_post_csrf_and_origin_required(self):
        self.assertEqual(self.client.get("/api/accounts/profile/").status_code, 405)
        self.assertEqual(self.client.post("/api/accounts/profile/", {"nickname": "변경"}).status_code, 403)
        token = self.client.get("/api/accounts/session/").json()["csrfToken"]
        self.assertEqual(self.client.post("/api/accounts/profile/", {"nickname": "변경"}, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://external.example").status_code, 403)


class AccountPageTests(TestCase):
    def test_session_shows_only_current_member_public_profile(self):
        user=get_user_model().objects.create_user(username="my_account",nickname="내 닉네임",password="Orbit!2026-Account")
        get_user_model().objects.create_user(username="other_account",nickname="다른 회원")
        self.client.force_login(user)
        response=self.client.get("/api/accounts/session/")
        self.assertEqual(response.json()["user"],{"username":user.username,"nickname":user.nickname,"joinedAt":user.date_joined.isoformat()})
        self.assertIn("no-store",response["Cache-Control"])

    def test_logged_out_session_exposes_no_profile(self):
        user=get_user_model().objects.create_user(username="my_account")
        self.client.force_login(user)
        self.client.post("/api/accounts/logout/")
        self.assertIsNone(self.client.get("/api/accounts/session/").json()["user"])
