from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
MAX_AMOUNT=1_000_000_000_000
positive=[MinValueValidator(1),MaxValueValidator(MAX_AMOUNT)]

class Wallet(models.Model):
    member=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="wallet",verbose_name="회원")
    available=models.BigIntegerField("사용 가능한 보유금액",default=0)
    reserved=models.BigIntegerField("출금 신청 중인 금액",default=0)
    points=models.BigIntegerField("보유 포인트",default=0)
    class Meta:
        verbose_name="회원 잔액"
        verbose_name_plural="회원 잔액"
        constraints=[models.CheckConstraint(condition=models.Q(available__gte=0),name="wallet_available_nonnegative"),models.CheckConstraint(condition=models.Q(reserved__gte=0),name="wallet_reserved_nonnegative"),models.CheckConstraint(condition=models.Q(points__gte=0),name="wallet_points_nonnegative")]
    def __str__(self):return self.member.username

class MoneyRequest(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT="deposit","입금"
        WITHDRAW="withdraw","출금"
    class Status(models.TextChoices):
        PENDING="pending","승인 대기"
        APPROVED="approved","승인 완료"
        REJECTED="rejected","거절"
    member=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,verbose_name="회원")
    kind=models.CharField("구분",max_length=10,choices=Kind.choices)
    amount=models.BigIntegerField("금액",validators=positive)
    status=models.CharField("상태",max_length=10,choices=Status.choices,default=Status.PENDING)
    bonus_option = models.ForeignKey("DepositBonus", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="선택한 보너스")
    bonus_name = models.CharField("신청 시 보너스 이름", max_length=100, blank=True)
    bonus_percent = models.DecimalField("신청 시 보너스 (%)", max_digits=5, decimal_places=2, default=0)
    bonus_amount = models.BigIntegerField("보너스 지급액", default=0)
    bonus_destination = models.CharField("보너스 지급 대상", max_length=10, choices=[("balance", "보유금액"), ("points", "포인트")], default="balance")
    rolling_snapshot = models.JSONField("신청 시 롤링 조건", default=dict, blank=True)
    created_at=models.DateTimeField("신청일",auto_now_add=True)
    processed_at=models.DateTimeField("처리일",null=True,blank=True)
    processed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="processed_money_requests",verbose_name="처리 관리자")
    class Meta:
        verbose_name="입출금 신청"
        verbose_name_plural="입출금 신청"
        ordering=["-created_at","-pk"]
    def __str__(self):return f"{self.get_kind_display()} {self.member.username} {self.amount}"

class PointGrant(models.Model):
    member=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="point_grants",verbose_name="회원")
    amount=models.BigIntegerField("지급 포인트",validators=positive)
    reason=models.CharField("지급 사유",max_length=200)
    granted_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="granted_points",verbose_name="지급 관리자")
    created_at=models.DateTimeField("지급일",auto_now_add=True)
    class Meta:
        verbose_name="포인트 지급 내역"
        verbose_name_plural="포인트 지급 내역"
        ordering=["-created_at","-pk"]
    def __str__(self):return f"{self.member.username} {self.amount}P"

class PointConversion(models.Model):
    member=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,verbose_name="회원")
    points=models.BigIntegerField("전환 포인트",validators=positive)
    created_at=models.DateTimeField("전환일",auto_now_add=True)
    class Meta:
        verbose_name="포인트 전환 내역"
        verbose_name_plural="포인트 전환 내역"
        ordering=["-created_at","-pk"]

class WalletEntry(models.Model):
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT,related_name="entries",verbose_name="회원 잔액")
    kind=models.CharField("변경 구분",max_length=30)
    available_delta=models.BigIntegerField("보유금액 변경",default=0)
    reserved_delta=models.BigIntegerField("출금 예약 변경",default=0)
    points_delta=models.BigIntegerField("포인트 변경",default=0)
    reference=models.CharField("참조",max_length=60,unique=True)
    created_at=models.DateTimeField("기록일",auto_now_add=True)
    class Meta:
        verbose_name="잔액 변경 기록"
        verbose_name_plural="잔액 변경 기록"
        ordering=["-created_at","-pk"]


ROLLING_CATEGORIES = (
    ("sports_single", "스포츠 싱글"),
    ("sports_double", "스포츠 더블"),
    ("sports_multi", "스포츠 멀티"),
    ("minigame", "미니게임"),
    ("casino", "카지노"),
)


class DepositBonus(models.Model):
    class Destination(models.TextChoices):
        BALANCE = "balance", "보유금액"
        POINTS = "points", "포인트"

    name = models.CharField("보너스 이름", max_length=100)
    description = models.CharField("안내 문구", max_length=200, blank=True)
    bonus_percent = models.DecimalField(
        "입금 보너스 (%)", max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    destination = models.CharField("보너스 지급 대상", max_length=10, choices=Destination.choices, default=Destination.BALANCE)
    sports_single = models.PositiveIntegerField("스포츠 싱글 롤링 (%)", default=100, null=True, blank=True, validators=[MaxValueValidator(100000)])
    sports_double = models.PositiveIntegerField("스포츠 더블 롤링 (%)", default=100, null=True, blank=True, validators=[MaxValueValidator(100000)])
    sports_multi = models.PositiveIntegerField("스포츠 멀티 롤링 (%)", default=100, null=True, blank=True, validators=[MaxValueValidator(100000)])
    minigame = models.PositiveIntegerField("미니게임 롤링 (%)", default=100, null=True, blank=True, validators=[MaxValueValidator(100000)])
    casino = models.PositiveIntegerField("카지노 롤링 (%)", default=100, null=True, blank=True, validators=[MaxValueValidator(100000)])
    is_active = models.BooleanField("사용", default=True)
    sort_order = models.PositiveIntegerField("표시 순서", default=0)

    class Meta:
        verbose_name = "입금 보너스 설정"
        verbose_name_plural = "입금 보너스 설정"
        ordering = ["sort_order", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(bonus_percent__gte=0, bonus_percent__lte=100), name="deposit_bonus_percent_range")]

    def __str__(self):
        return self.name

    def rolling_values(self):
        return {key: getattr(self, key) for key, _ in ROLLING_CATEGORIES}


class DepositAccount(models.Model):
    bank_name = models.CharField("은행명", max_length=50)
    account_number = models.CharField("계좌번호", max_length=60)
    account_holder = models.CharField("예금주", max_length=100)
    instructions = models.TextField("안내 문구", blank=True)
    is_active = models.BooleanField("안내할 계좌", default=False)
    updated_at = models.DateTimeField("수정일", auto_now=True)

    class Meta:
        verbose_name = "입금 계좌 설정"
        verbose_name_plural = "입금 계좌 설정"
        constraints = [models.UniqueConstraint(fields=["is_active"], condition=models.Q(is_active=True), name="one_active_deposit_account")]

    def __str__(self):
        return f"{self.bank_name} · {self.account_holder}"


class DepositAccountRequest(models.Model):
    status = models.CharField("상태", max_length=10, choices=[("pending", "안내 대기"), ("replied", "안내 완료")], default="pending")
    responded_at = models.DateTimeField("안내일", null=True, blank=True)
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="replied_account_requests", verbose_name="안내 관리자")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="회원")
    created_at = models.DateTimeField("요청일", auto_now_add=True)
    account = models.ForeignKey(DepositAccount, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="안내 계좌")
    account_snapshot = models.JSONField("안내한 계좌 정보", default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member"], condition=models.Q(status="pending"), name="one_pending_account_request_per_member")]
        verbose_name = "입금 계좌 요청 내역"
        verbose_name_plural = "입금 계좌 요청 내역"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.member.username} · 계좌 요청"


class DepositRequest(MoneyRequest):
    class Meta:
        proxy = True
        verbose_name = "입금 요청"
        verbose_name_plural = "입금 요청"


class WithdrawalRequest(MoneyRequest):
    class Meta:
        proxy = True
        verbose_name = "출금 요청"
        verbose_name_plural = "출금 요청"
