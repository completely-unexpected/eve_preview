from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac


class User(AbstractUser):
    class Status(models.TextChoices):
        PENDING = "pending", "승인 대기"
        APPROVED = "approved", "승인 완료"
        SUSPENDED = "suspended", "이용 정지"

    nickname = models.CharField("닉네임", max_length=30, blank=True)
    account_status = models.CharField(
        "가입 상태", max_length=16, choices=Status.choices, default=Status.APPROVED,
    )
    board_last_post_at = models.DateTimeField(null=True, blank=True, editable=False)
    session_revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    def clean(self):
        super().clean()
        if (self.is_staff or self.is_superuser) and self.account_status != self.Status.APPROVED:
            raise ValidationError({"account_status": "관리자 계정은 승인 대기나 이용 정지로 변경할 수 없습니다."})

    def save(self, *args, **kwargs):
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
