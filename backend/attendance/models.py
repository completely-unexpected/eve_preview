from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

amount_validators = [MinValueValidator(0), MaxValueValidator(1_000_000_000_000)]


class AttendanceSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    is_active = models.BooleanField("출석체크 사용", default=True)
    minimum_deposit = models.PositiveBigIntegerField("당일 최소 승인 입금액", default=100000, validators=amount_validators)
    daily_points = models.PositiveBigIntegerField("매일 출석 포인트", default=1000, validators=amount_validators)
    streak_days = models.PositiveSmallIntegerField("연속 출석 일수", default=7, validators=[MinValueValidator(1), MaxValueValidator(31)])
    streak_points = models.PositiveBigIntegerField("연속 출석 포인트 (월 1회)", default=40000, validators=amount_validators)
    monthly_days = models.PositiveSmallIntegerField("월 누적 출석 일수", default=20, validators=[MinValueValidator(1), MaxValueValidator(31)])
    monthly_points = models.PositiveBigIntegerField("월 누적 출석 포인트 (월 1회)", default=70000, validators=amount_validators)

    class Meta:
        verbose_name = "출석 조건·포인트 설정"
        verbose_name_plural = "출석 조건·포인트 설정"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="attendance_single_settings")]

    def __str__(self):
        return "출석체크 설정"


class Attendance(models.Model):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="회원")
    date = models.DateField("출석일 (한국 시간)")
    deposit_amount = models.PositiveBigIntegerField("당일 승인 입금 원금")
    streak = models.PositiveSmallIntegerField("월 내 연속 출석 일수")
    awarded_points = models.PositiveBigIntegerField("총 지급 포인트")
    conditions = models.JSONField("출석 시 적용 조건", default=dict)
    created_at = models.DateTimeField("체크 시간", auto_now_add=True)

    class Meta:
        verbose_name = "출석 기록"
        verbose_name_plural = "출석 기록"
        ordering = ["-date", "-pk"]
        constraints = [models.UniqueConstraint(fields=["member", "date"], name="one_attendance_per_day")]

    def __str__(self):
        return f"{self.member.username} · {self.date}"


class AttendanceReward(models.Model):
    class Kind(models.TextChoices):
        DAILY = "daily", "매일 출석"
        STREAK = "streak", "연속 출석"
        MONTHLY = "monthly", "월 누적 출석"

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="회원")
    attendance = models.ForeignKey(Attendance, on_delete=models.PROTECT, related_name="rewards", verbose_name="출석 기록")
    month = models.DateField("해당 월")
    kind = models.CharField("지급 구분", max_length=10, choices=Kind.choices)
    points = models.PositiveBigIntegerField("지급 포인트")
    created_at = models.DateTimeField("지급일", auto_now_add=True)

    class Meta:
        verbose_name = "출석 포인트 지급 내역"
        verbose_name_plural = "출석 포인트 지급 내역"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["attendance", "kind"], name="one_reward_per_attendance_kind"),
            models.UniqueConstraint(fields=["member", "month", "kind"], condition=models.Q(kind__in=["streak", "monthly"]), name="one_attendance_milestone_per_month"),
        ]
