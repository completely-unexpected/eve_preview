from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from accounts.models import MemberLevel


class MemberLimitTests(TestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="limits_member", nickname="한도 회원")
        self.level = MemberLevel.objects.create(number=2, name="레벨 2", single_max=5000000, multi_max=7000000)
        self.client.force_login(self.member)

    def test_default_level_inheritance_and_member_overrides(self):
        self.assertEqual(self.member.level_id, 1)
        self.member.level = self.level
        self.member.single_max = 4000000
        self.member.full_clean()
        self.member.save()
        data = self.client.get("/api/accounts/details/").json()
        self.assertEqual(data["user"]["level"], 2)
        self.assertEqual(data["limits"]["single_max"], 4000000)
        self.assertEqual(data["limits"]["multi_max"], 7000000)
        self.assertNotIn("password", data["user"])
        self.assertIn("no-store", self.client.get("/api/accounts/details/")["Cache-Control"])
        self.assertEqual(Client().get("/api/accounts/details/").status_code, 401)

    def test_member_cannot_change_level_or_limits_through_profile(self):
        response = self.client.post("/api/accounts/profile/", {
            "nickname": "변경된 닉네임", "level": 2, "single_max": 999999999,
        })
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.nickname, "변경된 닉네임")
        self.assertEqual(self.member.level_id, 1)
        self.assertIsNone(self.member.single_max)

    def test_invalid_ranges_are_rejected_for_levels_and_members(self):
        self.level.single_min = 6000000
        with self.assertRaises(ValidationError):
            self.level.full_clean()
        self.member.single_min = 4000000
        with self.assertRaises(ValidationError):
            self.member.full_clean()

    def test_admin_updates_level_defaults_and_can_edit_member_assignment(self):
        admin = get_user_model().objects.create_superuser(username="limits_admin")
        adminclient = Client()
        adminclient.force_login(admin)
        self.member.level = self.level
        self.member.save()
        response = adminclient.post("/admin/accounts/memberlevel/2/change/", {
            "name": "레벨 2 수정", "single_min": 10000, "single_max": 6000000,
            "single_payout": 15000000, "multi_min": 10000, "multi_max": 8000000,
            "multi_payout": 20000000, "_save": "저장",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/api/accounts/details/").json()["limits"]["single_max"], 6000000)
        response = adminclient.get(f"/admin/accounts/user/{self.member.pk}/change/")
        self.assertContains(response, 'id="id_level"')
        self.assertContains(response, 'id="id_single_max"')
