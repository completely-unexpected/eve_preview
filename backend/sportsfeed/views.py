from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from . import services


@never_cache
@require_GET
def leagues(request):
    try:
        items = services.leagues()
    except services.ProviderError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=503)
    default = next((item["key"] for item in items if item["key"] == "soccer_epl"), items[0]["key"] if items else "")
    return JsonResponse({"ok": True, "items": items, "defaultLeague": default, "source": "The Odds API"})


@never_cache
@require_GET
def events(request):
    try:
        result = services.events(request.GET.get("league", "soccer_epl"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    except services.ProviderError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=503)
    return JsonResponse({"ok": True, **result})


@never_cache
@require_GET
def board(request):
    from .models import FeedSnapshot
    snapshot = FeedSnapshot.objects.filter(pk=1).first()
    if not snapshot or not snapshot.payload:
        return JsonResponse({"ok": False, "message": "전체 경기·배당을 준비하고 있습니다."}, status=503)
    return JsonResponse({"ok": True, **snapshot.payload, "fetchedAt": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None, "syncing": snapshot.syncing, "canLoadExtra": request.user.is_authenticated and request.user.is_staff and request.user.has_perm("sportsfeed.change_feedsnapshot")})


from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

@never_cache
@require_POST
@csrf_protect
def extra_markets(request):
    from .extra import load_extra
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "관리자로 로그인해 주세요."}, status=401)
    try:
        event, remaining = load_extra(request.POST.get("event_id"), request.user)
    except PermissionError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=403)
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    except services.ProviderError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=503)
    return JsonResponse({"ok": True, "event": event, "remainingCredits": remaining})


@never_cache
@require_GET
def permissions(request):
    return JsonResponse({"ok": True, "canLoadExtra": request.user.is_authenticated and request.user.is_active and request.user.is_staff and request.user.has_perm("sportsfeed.change_feedsnapshot")})
