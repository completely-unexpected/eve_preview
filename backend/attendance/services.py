from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from wallet.models import MAX_AMOUNT, MoneyRequest, Wallet
from wallet.services import entry, wallet_for
from .models import Attendance, AttendanceReward, AttendanceSettings

KST = ZoneInfo("Asia/Seoul")


def today_kst():
    return timezone.now().astimezone(KST).date()


def approved_deposits(member, day):
    start = datetime.combine(day, time.min, tzinfo=KST)
    end = start + timedelta(days=1)
    return MoneyRequest.objects.filter(
        member=member, kind="deposit", status="approved", processed_at__gte=start, processed_at__lt=end,
    ).aggregate(amount=Sum("amount"))["amount"] or 0


def rules_data(settings):
    return {
        "active": settings.is_active, "minimumDeposit": settings.minimum_deposit,
        "dailyPoints": settings.daily_points, "streakDays": settings.streak_days,
        "streakPoints": settings.streak_points, "monthlyDays": settings.monthly_days,
        "monthlyPoints": settings.monthly_points,
    }


@transaction.atomic
def check_in(member):
    day = today_kst()
    month = day.replace(day=1)
    settings = AttendanceSettings.objects.select_for_update().get(pk=1)
    if not settings.is_active:
        raise ValidationError("출석체크가 일시 중지되었습니다.")
    wallet = wallet_for(member)
    Wallet.objects.select_for_update().get(pk=wallet.pk)
    if Attendance.objects.filter(member=member, date=day).exists():
        raise ValidationError("오늘은 이미 출석체크를 완료했습니다.")
    deposit = approved_deposits(member, day)
    if deposit < settings.minimum_deposit:
        raise ValidationError(f"오늘 승인된 입금 원금이 {settings.minimum_deposit:,}원 이상이어야 출석할 수 있습니다.")
    previous = Attendance.objects.filter(member=member, date=day - timedelta(days=1), date__gte=month).first()
    streak = previous.streak + 1 if previous else 1
    count = Attendance.objects.filter(member=member, date__gte=month, date__lt=day).count() + 1
    awards = [(AttendanceReward.Kind.DAILY, settings.daily_points)]
    claimed = set(AttendanceReward.objects.filter(member=member, month=month).values_list("kind", flat=True))
    if streak >= settings.streak_days and AttendanceReward.Kind.STREAK not in claimed:
        awards.append((AttendanceReward.Kind.STREAK, settings.streak_points))
    if count >= settings.monthly_days and AttendanceReward.Kind.MONTHLY not in claimed:
        awards.append((AttendanceReward.Kind.MONTHLY, settings.monthly_points))
    total = sum(points for _, points in awards)
    record = Attendance.objects.create(
        member=member, date=day, deposit_amount=deposit, streak=streak,
        awarded_points=total, conditions=rules_data(settings),
    )
    changed = Wallet.objects.filter(pk=wallet.pk, points__lte=MAX_AMOUNT - total).update(points=F("points") + total)
    if not changed:
        raise ValidationError("포인트 잔액 상한을 초과하여 출석 포인트를 지급할 수 없습니다. 관리자에게 문의해 주세요.")
    for kind, points in awards:
        AttendanceReward.objects.create(member=member, attendance=record, month=month, kind=kind, points=points)
        entry(wallet, "attendance_" + kind, f"attendance:{record.pk}:{kind}", points=points)
    return record
