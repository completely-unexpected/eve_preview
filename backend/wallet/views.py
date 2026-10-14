from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import DepositAccountRequest, DepositBonus, MoneyRequest, PointConversion, PointGrant, ROLLING_CATEGORIES
from .services import convert_points, request_deposit_account, request_money, wallet_for


def unauthorized():
    return JsonResponse({"ok": False, "message": "로그인 후 이용해 주세요."}, status=401)


def error(exc):
    return JsonResponse({"ok": False, "message": exc.messages[0]}, status=400)


def request_data(record):
    return {
        "id": record.pk, "kind": record.kind, "amount": record.amount,
        "status": record.status, "createdAt": record.created_at.isoformat(),
        "bonusName": record.bonus_name, "bonusPercent": str(record.bonus_percent),
        "bonusAmount": record.bonus_amount, "bonusDestination": record.bonus_destination,
        "rolling": record.rolling_snapshot,
    }


def bonus_data(option):
    return {
        "id": option.pk, "name": option.name, "description": option.description,
        "bonusPercent": str(option.bonus_percent),
        "bonusBasisPoints": int(option.bonus_percent * 100),
        "destination": option.destination, "rolling": option.rolling_values(),
    }


@never_cache
@require_GET
def overview(request):
    if not request.user.is_authenticated:
        return unauthorized()
    wallet = wallet_for(request.user)
    page = Paginator(MoneyRequest.objects.filter(member=request.user), 20).get_page(request.GET.get("page"))
    grants = PointGrant.objects.filter(member=request.user)[:10]
    conversions = PointConversion.objects.filter(member=request.user)[:10]
    return JsonResponse({
        "ok": True, "available": wallet.available, "reserved": wallet.reserved, "points": wallet.points,
        "requests": [request_data(item) for item in page], "page": page.number, "pages": page.paginator.num_pages,
        "grants": [{"points": g.amount, "reason": g.reason, "createdAt": g.created_at.isoformat()} for g in grants],
        "conversions": [{"points": c.points, "createdAt": c.created_at.isoformat()} for c in conversions],
        "bonuses": [bonus_data(option) for option in DepositBonus.objects.filter(is_active=True)],
        "rollingCategories": [{"key": key, "label": label} for key, label in ROLLING_CATEGORIES],
        "memberName": request.user.nickname or request.user.username,
    })


@never_cache
@require_POST
@csrf_protect
def apply(request):
    if not request.user.is_authenticated:
        return unauthorized()
    try:
        record = request_money(request.user, request.POST.get("kind"), request.POST.get("amount"), request.POST.get("bonus_id"))
    except ValidationError as exc:
        return error(exc)
    return JsonResponse({"ok": True, "request": request_data(record)}, status=201)


@never_cache
@require_POST
@csrf_protect
def convert(request):
    if not request.user.is_authenticated:
        return unauthorized()
    try:
        record = convert_points(request.user, request.POST.get("points"))
    except ValidationError as exc:
        return error(exc)
    return JsonResponse({"ok": True, "converted": record.points}, status=201)


def account_request_data(record):
    return {"id": record.pk, "status": record.status, "createdAt": record.created_at.isoformat()}


@never_cache
@require_http_methods(["GET", "POST"])
@csrf_protect
def account_request(request):
    if not request.user.is_authenticated:
        return unauthorized()
    if request.method == "POST":
        record = request_deposit_account(request.user)
    else:
        record = DepositAccountRequest.objects.filter(member=request.user).first()
    return JsonResponse({
        "ok": True, "request": account_request_data(record) if record else None,
        "account": record.account_snapshot if record and record.status == "replied" else None,
    }, status=201 if request.method == "POST" else 200)
