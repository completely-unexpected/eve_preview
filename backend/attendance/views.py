from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from wallet.models import Wallet
from .models import Attendance, AttendanceReward, AttendanceSettings
from .services import approved_deposits, check_in, rules_data, today_kst


def unauthorized():
    return JsonResponse({"ok": False, "message": "로그인 후 출석체크를 이용해 주세요."}, status=401)


@never_cache
@require_GET
def overview(request):
    if not request.user.is_authenticated:
        return unauthorized()
    today = today_kst()
    try:
        month = date(int(request.GET.get("year", today.year)), int(request.GET.get("month", today.month)), 1)
        if not 2000 <= month.year <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "message": "조회할 연월이 올바르지 않습니다."}, status=400)
    end = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    records = list(Attendance.objects.filter(member=request.user, date__gte=month, date__lt=end))
    rewards = AttendanceReward.objects.filter(member=request.user, month=month).select_related("attendance")
    settings = AttendanceSettings.objects.get(pk=1)
    deposit = approved_deposits(request.user, today)
    checked = Attendance.objects.filter(member=request.user, date=today).exists()
    eligible = settings.is_active and not checked and deposit >= settings.minimum_deposit
    if checked:
        message = "오늘 출석체크를 완료했습니다."
    elif not settings.is_active:
        message = "출석체크가 일시 중지되었습니다."
    elif eligible:
        message = "오늘 출석체크가 가능합니다!"
    else:
        message = f"오늘 승인된 입금이 {max(settings.minimum_deposit - deposit, 0):,}원 더 필요합니다."
    wallet = Wallet.objects.filter(member=request.user).first()
    return JsonResponse({
        "ok": True, "today": today.isoformat(), "year": month.year, "month": month.month,
        "rules": rules_data(settings), "checkedToday": checked, "eligible": eligible, "message": message,
        "todayDeposit": deposit, "points": wallet.points if wallet else 0,
        "days": [{"date": record.date.isoformat(), "points": record.awarded_points, "streak": record.streak} for record in records],
        "monthlyCount": len(records), "longestStreak": max((record.streak for record in records), default=0),
        "monthlyPoints": rewards.aggregate(total=Sum("points"))["total"] or 0,
        "rewards": [{"date": reward.attendance.date.isoformat(), "kind": reward.get_kind_display(), "points": reward.points} for reward in rewards],
    })


@never_cache
@require_POST
@csrf_protect
def check(request):
    if not request.user.is_authenticated:
        return unauthorized()
    try:
        record = check_in(request.user)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "message": exc.messages[0]}, status=400)
    except IntegrityError:
        return JsonResponse({"ok": False, "message": "이미 처리된 출석입니다. 새로고침해 주세요."}, status=409)
    return JsonResponse({"ok": True, "message": f"출석 완료! {record.awarded_points:,}P가 지급되었습니다.", "points": record.awarded_points}, status=201)
