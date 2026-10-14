from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from wallet.models import MoneyRequest, Wallet, WalletEntry
from .models import Attendance, AttendanceReward, AttendanceSettings
from .services import check_in, today_kst


class AttendanceTests(TestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="attendance_member")
        self.other = get_user_model().objects.create_user(username="other_attendance")
        self.rules = AttendanceSettings.objects.get(pk=1)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.member)

    def clock(self, day, month=10):
        return patch("attendance.services.timezone.now", return_value=datetime(2026, month, day, 3, tzinfo=dt_timezone.utc))

    def deposit(self, amount, status="approved", day=14):
        return MoneyRequest.objects.create(member=self.member, kind="deposit", amount=amount, status=status,
                                           processed_at=datetime(2026, 10, day, 3, tzinfo=dt_timezone.utc))

    def post(self, data=None):
        csrf = self.client.get("/api/accounts/session/").json()["csrfToken"]
        return self.client.post("/api/attendance/check/", data or {}, HTTP_X_CSRFTOKEN=csrf)

    def disable_deposit_requirement(self):
        self.rules.minimum_deposit = 0
        self.rules.save()

    def test_only_today_approved_principal_counts_and_split_deposits_qualify(self):
        with self.clock(14):
            self.deposit(999999, "pending")
            self.deposit(999999, "rejected")
            self.deposit(999999, day=13)
            self.assertEqual(self.post().status_code, 400)
            self.deposit(60000)
            self.assertEqual(self.post().status_code, 400)
            deposit = self.deposit(40000)
            deposit.bonus_amount = 5000
            deposit.save()
            self.assertEqual(self.client.get("/api/attendance/").json()["todayDeposit"], 100000)
            self.assertEqual(self.post({"date": "2026-01-01", "points": 999999}).status_code, 201)
            self.assertEqual(Attendance.objects.get().date.isoformat(), "2026-10-14")
            self.assertEqual(Attendance.objects.get().deposit_amount, 100000)
            self.assertEqual(Wallet.objects.get(member=self.member).points, 1000)

    def test_repeat_check_is_rejected_without_duplicate_rewards(self):
        self.disable_deposit_requirement()
        with self.clock(14):
            check_in(self.member)
            self.assertEqual(self.post().status_code, 400)
            self.assertEqual(Attendance.objects.count(), 1)
            self.assertEqual(AttendanceReward.objects.count(), 1)
            self.assertEqual(WalletEntry.objects.filter(kind="attendance_daily").count(), 1)
            self.assertEqual(Wallet.objects.get(member=self.member).points, 1000)

    def test_streak_and_monthly_awards_are_paid_once_per_month(self):
        self.disable_deposit_requirement()
        for day in range(1, 22):
            with self.clock(day):
                record = check_in(self.member)
                if day == 7: self.assertEqual(record.awarded_points, 41000)
                if day == 20: self.assertEqual(record.awarded_points, 71000)
        self.assertEqual(Wallet.objects.get(member=self.member).points, 131000)
        self.assertEqual(AttendanceReward.objects.filter(kind="streak").count(), 1)
        self.assertEqual(AttendanceReward.objects.filter(kind="monthly").count(), 1)
        self.assertEqual(sum(WalletEntry.objects.values_list("points_delta", flat=True)), 131000)
        with self.clock(1, 11):
            record = check_in(self.member)
            self.assertEqual(record.streak, 1)
            self.assertEqual(record.awarded_points, 1000)

    def test_gap_resets_consecutive_count(self):
        self.disable_deposit_requirement()
        with self.clock(1): check_in(self.member)
        with self.clock(3): self.assertEqual(check_in(self.member).streak, 1)

    def test_korea_midnight_boundary_creates_a_new_day(self):
        self.disable_deposit_requirement()
        before = datetime(2026, 10, 13, 14, 59, 59, tzinfo=dt_timezone.utc)
        after = before + timedelta(seconds=1)
        with patch("attendance.services.timezone.now", return_value=before):
            self.assertEqual(today_kst().isoformat(), "2026-10-13")
            check_in(self.member)
        with patch("attendance.services.timezone.now", return_value=after):
            self.assertEqual(today_kst().isoformat(), "2026-10-14")
            check_in(self.member)
        self.assertEqual(Wallet.objects.get(member=self.member).points, 2000)

    def test_unauthenticated_csrf_and_member_isolation(self):
        self.assertEqual(Client().get("/api/attendance/").status_code, 401)
        self.assertEqual(Client().post("/api/attendance/check/").status_code, 401)
        self.assertEqual(self.client.post("/api/attendance/check/").status_code, 403)
        self.assertEqual(self.client.get("/api/attendance/check/").status_code, 405)
        self.disable_deposit_requirement()
        with self.clock(14):
            check_in(self.other)
            response = self.client.get("/api/attendance/?year=2026&month=10")
            self.assertEqual(response.json()["days"], [])
            self.assertEqual(response.json()["monthlyPoints"], 0)
            self.assertIn("no-store", response["Cache-Control"])

    def test_admin_can_change_rules_without_changing_past_rewards(self):
        self.disable_deposit_requirement()
        with self.clock(1): first = check_in(self.member)
        admin = get_user_model().objects.create_superuser(username="attendance_admin")
        adminclient = Client()
        adminclient.force_login(admin)
        response = adminclient.post("/admin/attendance/attendancesettings/1/change/", {
            "is_active": "on", "minimum_deposit": 0, "daily_points": 2500,
            "streak_days": 2, "streak_points": 3000, "monthly_days": 3, "monthly_points": 4000, "_save": "저장",
        })
        self.assertEqual(response.status_code, 302)
        with self.clock(2): self.assertEqual(check_in(self.member).awarded_points, 5500)
        with self.clock(3): self.assertEqual(check_in(self.member).awarded_points, 6500)
        first.refresh_from_db()
        self.assertEqual(first.conditions["dailyPoints"], 1000)
        self.assertEqual(Wallet.objects.get(member=self.member).points, 13000)

    def test_disabled_attendance_and_overflow_do_not_create_records(self):
        self.disable_deposit_requirement()
        self.rules.is_active = False
        self.rules.save()
        with self.clock(14):
            with self.assertRaises(ValidationError): check_in(self.member)
        self.rules.is_active = True
        self.rules.save()
        Wallet.objects.create(member=self.member, points=1000000000000)
        with self.clock(14):
            with self.assertRaises(ValidationError): check_in(self.member)
        self.assertEqual(Attendance.objects.count(), 0)
        self.assertEqual(AttendanceReward.objects.count(), 0)
        self.assertEqual(WalletEntry.objects.count(), 0)

    def test_selected_month_history_and_invalid_month(self):
        self.disable_deposit_requirement()
        with self.clock(14): check_in(self.member)
        with self.clock(1, 11):
            self.client.force_login(self.member)
            data = self.client.get("/api/attendance/?year=2026&month=10").json()
            self.assertEqual(data["monthlyCount"], 1)
            self.assertEqual(data["days"][0]["date"], "2026-10-14")
            self.assertEqual(data["today"], "2026-11-01")
            self.assertEqual(self.client.get("/api/attendance/?month=13").status_code, 400)
            self.assertEqual(self.client.get("/api/attendance/?year=bad").status_code, 400)
