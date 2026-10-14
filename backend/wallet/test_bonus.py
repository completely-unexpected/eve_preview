from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from wallet.models import DepositAccount, DepositAccountRequest, DepositBonus, MoneyRequest, Wallet, WalletEntry
from wallet.services import decide, request_money, reply_deposit_account


class DepositBonusTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user(username="bonus_member", password="Orbit!2026-Bonus")
        self.admin = User.objects.create_superuser(username="bonus_admin", password="Orbit!2026-Admin")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.member)
        self.bonus = DepositBonus.objects.create(
            name="テスト <bonus>", bonus_percent=Decimal("7.25"), sports_single=300, minigame=400, casino=None,
        )

    def post(self, endpoint, data=None):
        csrf = self.client.get("/api/accounts/session/").json()["csrfToken"]
        return self.client.post("/api/wallet/" + endpoint, data or {}, HTTP_X_CSRFTOKEN=csrf)

    def test_bonus_preview_data_and_server_snapshot_remain_unchanged(self):
        response = self.client.get("/api/wallet/")
        option = next(item for item in response.json()["bonuses"] if item["id"] == self.bonus.pk)
        self.assertEqual(option["bonusBasisPoints"], 725)
        self.assertEqual(option["rolling"]["sports_single"], 300)
        self.assertIsNone(option["rolling"]["casino"])
        response = self.post("apply/", {"kind": "deposit", "amount": "1001", "bonus_id": self.bonus.pk, "bonus_amount": "999999"})
        self.assertEqual(response.status_code, 201)
        record = MoneyRequest.objects.get(pk=response.json()["request"]["id"])
        self.assertEqual(record.bonus_amount, 72)
        self.assertEqual(Wallet.objects.get(member=self.member).available, 0)
        self.bonus.bonus_percent = Decimal("50")
        self.bonus.sports_single = 900
        self.bonus.save()
        decide(record.pk, self.admin, True)
        self.assertEqual(Wallet.objects.get(member=self.member).available, 1073)
        self.assertEqual(record.rolling_snapshot["sports_single"], 300)
        self.assertEqual(record.bonus_percent, Decimal("7.25"))
        with self.assertRaises(ValidationError):
            decide(record.pk, self.admin, True)
        self.assertEqual(WalletEntry.objects.filter(kind="deposit_bonus").count(), 1)

    def test_point_destination_and_rejected_bonus_are_not_double_paid(self):
        self.bonus.destination = "points"
        self.bonus.bonus_percent = 10
        self.bonus.save()
        accepted = request_money(self.member, "deposit", 30000, self.bonus.pk)
        rejected = request_money(self.member, "deposit", 50000, self.bonus.pk)
        decide(rejected.pk, self.admin, False)
        self.assertEqual(Wallet.objects.get(member=self.member).points, 0)
        decide(accepted.pk, self.admin, True)
        wallet = Wallet.objects.get(member=self.member)
        self.assertEqual((wallet.available, wallet.points), (30000, 3000))
        self.assertEqual(self.client.get("/api/wallet/").json()["grants"][0]["points"], 3000)

    def test_invalid_options_and_zero_percent_custom_conditions(self):
        for option_id in ("bad", "99999999999999999999999999999999", "-1"):
            self.assertEqual(self.post("apply/", {"kind": "deposit", "amount": "1000", "bonus_id": option_id}).status_code, 400)
        self.bonus.is_active = False
        self.bonus.save()
        self.assertEqual(self.post("apply/", {"kind": "deposit", "amount": "1000", "bonus_id": self.bonus.pk}).status_code, 400)
        self.assertEqual(self.post("apply/", {"kind": "withdraw", "amount": "1000", "bonus_id": self.bonus.pk}).status_code, 400)
        self.assertEqual(MoneyRequest.objects.count(), 0)
        none = DepositBonus.objects.create(name="보너스 없음", bonus_percent=0, minigame=250)
        record = request_money(self.member, "deposit", 1000, none.pk)
        self.assertEqual(record.rolling_snapshot["minigame"], 250)
        self.assertEqual(record.bonus_amount, 0)
        decide(record.pk, self.admin, True)
        self.assertEqual(Wallet.objects.get(member=self.member).available, 1000)

    def test_admin_edits_rates_blank_means_unavailable_and_range_validated(self):
        self.client.force_login(self.admin)
        response = self.post_admin_bonus("10.50", "450", "")
        self.assertEqual(response.status_code, 302)
        self.bonus.refresh_from_db()
        self.assertEqual(self.bonus.bonus_percent, Decimal("10.50"))
        self.assertEqual(self.bonus.sports_single, 450)
        self.assertIsNone(self.bonus.casino)
        self.bonus.bonus_percent = 101
        with self.assertRaises(ValidationError):
            self.bonus.full_clean()

    def post_admin_bonus(self, percent, rolling, casino):
        path = f"/admin/wallet/depositbonus/{self.bonus.pk}/change/"
        self.client.get(path)
        csrf = self.client.cookies["csrftoken"].value
        return self.client.post(path, {
            "name": "관리자 설정", "description": "조건 설명", "bonus_percent": percent,
            "destination": "balance", "sports_single": rolling, "sports_double": 100,
            "sports_multi": 100, "minigame": 400, "casino": casino, "sort_order": 0,
            "is_active": "on", "_save": "저장",
        }, HTTP_X_CSRFTOKEN=csrf)

    def test_bonus_overflow_rolls_back_every_change(self):
        Wallet.objects.create(member=self.member, available=999999999999)
        record = request_money(self.member, "deposit", 1000, self.bonus.pk)
        with self.assertRaises(ValidationError):
            decide(record.pk, self.admin, True)
        record.refresh_from_db()
        self.assertEqual(record.status, "pending")
        self.assertEqual(Wallet.objects.get(member=self.member).available, 999999999999)
        self.assertEqual(WalletEntry.objects.count(), 0)

    def test_admin_separates_deposit_and_withdrawal_requests(self):
        accepted = request_money(self.member, 'deposit', 30000)
        decide(accepted.pk, self.admin, True)
        request_money(self.member, 'withdraw', 1000)
        self.client.force_login(self.admin)
        response = self.client.get('/admin/wallet/depositrequest/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cl'].queryset.values_list('kind', flat=True)), ['deposit'])
        response = self.client.get('/admin/wallet/withdrawalrequest/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cl'].queryset.values_list('kind', flat=True)), ['withdraw'])


class DepositAccountTests(TestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="account_member")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.member)

    def post(self):
        csrf = self.client.get("/api/accounts/session/").json()["csrfToken"]
        return self.client.post("/api/wallet/account-request/", HTTP_X_CSRFTOKEN=csrf)

    def test_only_active_account_is_returned_on_authenticated_request(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['request']['status'], 'pending')
        self.assertIsNone(response.json()['account'])
        self.post()
        self.assertEqual(DepositAccountRequest.objects.count(), 1)
        hidden = DepositAccount.objects.create(bank_name="비활성 테스트 은행", account_number="HIDDEN-000", account_holder="테스트", is_active=False)
        admin = get_user_model().objects.create_superuser(username='account_admin')
        log = DepositAccountRequest.objects.get()
        with self.assertRaises(ValidationError):
            reply_deposit_account(log.pk, hidden.pk, admin)
        account = DepositAccount.objects.create(bank_name="테스트 은행", account_number="TEST-123-456", account_holder="테스트 예금주", is_active=True)
        overview = self.client.get("/api/wallet/")
        self.assertNotContains(overview, account.account_number)
        adminclient = Client()
        adminclient.force_login(admin)
        response = adminclient.post(f'/admin/wallet/depositaccountrequest/{log.pk}/change/', {'account': account.pk, '_save': '저장'})
        self.assertEqual(response.status_code, 302)
        response = self.client.get('/api/wallet/account-request/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account"]["accountNumber"], account.account_number)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotContains(response, hidden.account_number)
        log = DepositAccountRequest.objects.get()
        self.assertEqual(log.member, self.member)
        account.account_number = "TEST-CHANGED"
        account.save()
        log.refresh_from_db()
        self.assertEqual(log.account_snapshot["accountNumber"], "TEST-123-456")
        other = get_user_model().objects.create_user(username='other_account_member')
        otherclient = Client()
        otherclient.force_login(other)
        self.assertIsNone(otherclient.get('/api/wallet/account-request/').json()['request'])
        with self.assertRaises(ValidationError):
            reply_deposit_account(log.pk, account.pk, admin)

    def test_account_access_csrf_and_single_active_validation(self):
        self.assertEqual(Client().post("/api/wallet/account-request/").status_code, 401)
        self.assertEqual(self.client.post("/api/wallet/account-request/").status_code, 403)
        self.assertEqual(self.client.get("/api/wallet/account-request/").status_code, 200)
        DepositAccount.objects.create(bank_name="테스트", account_number="TEST-001", account_holder="테스트", is_active=True)
        second = DepositAccount(bank_name="두 번째", account_number="TEST-002", account_holder="테스트", is_active=True)
        with self.assertRaises(ValidationError):
            second.full_clean()
