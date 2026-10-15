import uuid
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.crypto import salted_hmac


class MemberLevel(models.Model):
    number = models.PositiveSmallIntegerField("레벨", primary_key=True, validators=[MinValueValidator(1), MaxValueValidator(100)])
    name = models.CharField("레벨 이름", max_length=50)
    single_min = models.PositiveBigIntegerField("싱글 최소 베팅", default=10000, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)])
    single_max = models.PositiveBigIntegerField("싱글 최대 베팅", default=3000000, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)])
    single_payout = models.PositiveBigIntegerField("싱글 최대 당첨", default=10000000, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)])
    multi_min = models.PositiveBigIntegerField("멀티 최소 베팅", default=10000, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)])
    multi_max = models.PositiveBigIntegerField("멀티 최대 베팅", default=3000000, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)])
    multi_payout = models.PositiveBigIntegerField("멀티 최대 당첨", default=10000000, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)])

    class Meta:
        verbose_name = "레벨별 이용한도"
        verbose_name_plural = "레벨별 이용한도"
        ordering = ["number"]
        constraints = [
            models.CheckConstraint(condition=models.Q(single_min__lte=models.F("single_max")), name="level_single_min_max"),
            models.CheckConstraint(condition=models.Q(multi_min__lte=models.F("multi_max")), name="level_multi_min_max"),
        ]

    def __str__(self):
        return f"레벨 {self.number} · {self.name}"

    def clean(self):
        super().clean()
        errors = {}
        for kind in ("single", "multi"):
            minimum = getattr(self, kind + "_min")
            maximum = getattr(self, kind + "_max")
            if minimum is not None and maximum is not None and minimum > maximum:
                errors[kind + "_min"] = "최소 베팅은 최대 베팅보다 클 수 없습니다."
        if errors:
            raise ValidationError(errors)


class User(AbstractUser):
    legal_name = models.CharField('이름',max_length=100,blank=True)
    phone_number = models.CharField('전화번호',max_length=30,blank=True)
    wallet_number = models.CharField('지갑번호',max_length=100,blank=True)
    admin_notes = models.TextField('비고',blank=True,max_length=10000)
    wallet_name = models.CharField('지갑명',max_length=100,default='기본 지갑')
    referrer = models.ForeignKey('self',verbose_name='회원 추천인',on_delete=models.SET_NULL,null=True,blank=True,related_name='recommended_members')
    class Status(models.TextChoices):
        PENDING = "pending", "승인 대기"
        APPROVED = "approved", "승인 완료"
        SUSPENDED = "suspended", "이용 정지"

    level = models.ForeignKey(MemberLevel, on_delete=models.PROTECT, null=True, blank=True, verbose_name="레벨", help_text="신규 회원의 기본 레벨은 1입니다.")
    single_min = models.PositiveBigIntegerField("싱글 최소 베팅 예외 한도", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)], help_text="빈칸이면 레벨 설정을 따릅니다.")
    single_max = models.PositiveBigIntegerField("싱글 최대 베팅 예외 한도", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)], help_text="빈칸이면 레벨 설정을 따릅니다.")
    single_payout = models.PositiveBigIntegerField("싱글 최대 당첨 예외 한도", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)], help_text="빈칸이면 레벨 설정을 따릅니다.")
    multi_min = models.PositiveBigIntegerField("멀티 최소 베팅 예외 한도", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)], help_text="빈칸이면 레벨 설정을 따릅니다.")
    multi_max = models.PositiveBigIntegerField("멀티 최대 베팅 예외 한도", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)], help_text="빈칸이면 레벨 설정을 따릅니다.")
    multi_payout = models.PositiveBigIntegerField("멀티 최대 당첨 예외 한도", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(1000000000000)], help_text="빈칸이면 레벨 설정을 따릅니다.")
    partner = models.ForeignKey("PartnerAccount", verbose_name="추천인 / 하위협력사", related_name="members", on_delete=models.PROTECT, null=True, blank=True)
    nickname = models.CharField("닉네임", max_length=30, blank=True)
    account_status = models.CharField(
        "가입 상태", max_length=16, choices=Status.choices, default=Status.APPROVED,
    )
    board_last_post_at = models.DateTimeField(null=True, blank=True, editable=False)
    session_revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    def clean(self):
        super().clean()
        limits = self.effective_limits()
        for kind in ("single", "multi"):
            if limits[kind + "_min"] > limits[kind + "_max"]:
                raise ValidationError({kind + "_min": "최소 베팅은 최대 베팅보다 클 수 없습니다."})
        if self.pk and self.referrer_id == self.pk:
            raise ValidationError({'referrer':'본인을 추천인으로 지정할 수 없습니다.'})
        if (self.is_staff or self.is_superuser) and self.account_status != self.Status.APPROVED:
            raise ValidationError({"account_status": "관리자 계정은 승인 대기나 이용 정지로 변경할 수 없습니다."})

    def save(self, *args, **kwargs):
        if self._state.adding and self.level_id is None and MemberLevel.objects.filter(pk=1).exists():
            self.level_id = 1
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "account_status" in update_fields or "is_active" in update_fields:
            if self.pk and self.account_status == self.Status.SUSPENDED:
                if type(self).objects.filter(pk=self.pk).exclude(account_status=self.Status.SUSPENDED).exists():
                    self.session_revoked_at = timezone.now()
                    if update_fields is not None:
                        update_fields = set(update_fields) | {"session_revoked_at"}
            self.is_active = self.account_status == self.Status.APPROVED
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"is_active"}
        super().save(*args, **kwargs)

    def effective_limits(self):
        defaults = {'single_min': 10000, 'single_max': 3000000, 'single_payout': 10000000, 'multi_min': 10000, 'multi_max': 3000000, 'multi_payout': 10000000}
        level = self.level if self.level_id is not None else MemberLevel.objects.filter(pk=1).first()
        return {
            key: getattr(self, key) if getattr(self, key) is not None else (getattr(level, key) if level else value)
            for key, value in defaults.items()
        }

    def _get_session_auth_hash(self, secret=None):
        original = super()._get_session_auth_hash(secret=secret)
        if self.session_revoked_at is None:
            return original
        return salted_hmac(
            "accounts.User.session_revocation", original + self.session_revoked_at.isoformat(),
            secret=secret, algorithm="sha256",
        ).hexdigest()


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    blocked_until = models.DateTimeField(null=True, blank=True)


def partner_code():
    return uuid.uuid4().hex


class PartnerAccount(models.Model):
    username = models.CharField("협력사 아이디", max_length=150, unique=True, validators=[UnicodeUsernameValidator()])
    name = models.CharField("협력사명", max_length=100)
    password = models.CharField(max_length=128, editable=False)
    referral_code = models.CharField("추천 코드", max_length=32, unique=True, editable=False, default=partner_code)
    is_active = models.BooleanField("사용 가능", default=True)
    session_version = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField("생성일", auto_now_add=True)
    last_login = models.DateTimeField("최근 로그인", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "하위협력사 계정"
        verbose_name_plural = "하위협력사 계정"
        ordering = ["username"]

    def __str__(self):
        return f"{self.name} ({self.username})"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)
        self.session_version = uuid.uuid4()

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def session_hash(self):
        return salted_hmac("accounts.partner_session", self.password + str(self.session_version) + str(self.is_active), algorithm="sha256").hexdigest()

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.referral_code = str(self.referral_code).replace("-", "")
        if self.pk and type(self).objects.filter(pk=self.pk).exclude(is_active=self.is_active).exists():
            self.session_version = uuid.uuid4()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"session_version"}
        super().save(*args, **kwargs)
