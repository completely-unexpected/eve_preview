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
    from catalog.league_names import localize_leagues
    items = localize_leagues(items)
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
    from catalog.league_names import localize_events
    result = {**result, "items":localize_events(result.get("items", []))}
    return JsonResponse({"ok": True, **result})


@never_cache
@require_GET
def board(request):
    from .models import FeedSnapshot
    from catalog.odds import apply_prices
    from catalog.league_names import localize_events, localize_leagues
    snapshot = FeedSnapshot.objects.filter(pk=1).first()
    if not snapshot or not snapshot.payload:
        return JsonResponse({"ok": False, "message": "전체 경기·배당을 준비하고 있습니다."}, status=503)
    return JsonResponse({"ok": True, **snapshot.payload, "items": localize_events(apply_prices(snapshot.payload.get('items', []), 'sports')), "leagues":localize_leagues(snapshot.payload.get("leagues", [])), "fetchedAt": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None, "syncing": snapshot.syncing, "canLoadExtra": request.user.is_authenticated and request.user.is_staff and request.user.has_perm("sportsfeed.change_feedsnapshot")})


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
        from catalog.odds import apply_prices
        event = apply_prices([event], 'sports')[0]
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


@never_cache
@require_GET
def slip_history(request, source='sports'):
    from django.core.paginator import Paginator
    from .models import DemoSlip
    from .slips import serialize
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'message': '로그인 후 이용해 주세요.'}, status=401)
    slips = DemoSlip.objects.filter(member=request.user)
    if source != 'all': slips = slips.filter(source=source)
    page = Paginator(slips.prefetch_related('results'), 10).get_page(request.GET.get('page'))
    return JsonResponse({'ok': True, 'items': [serialize(s) for s in page], 'page': page.number, 'pages': page.paginator.num_pages})


@never_cache
@require_GET
def my_slips(request):
    source=request.GET.get('source','all')
    if source not in ('all','sports','powerball'):
        return JsonResponse({'ok':False,'message':'올바르지 않은 게임 분류입니다.'},status=400)
    return slip_history(request, source=source)


@never_cache
@require_POST
@csrf_protect
def submit_slip(request, source='sports'):
    import json
    from django.core.exceptions import ValidationError
    from django.db import OperationalError
    from .slips import submit, serialize
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'message': '로그인 후 이용해 주세요.'}, status=401)
    if len(request.body) > 50000:
        return JsonResponse({'ok': False, 'message': '요청이 너무 큽니다.'}, status=400)
    try:
        data = json.loads(request.body)
        slip = submit(request.user, data, source=source)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'message': '요청 형식이 올바르지 않습니다.'}, status=400)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'message': exc.messages[0]}, status=400)
    except OperationalError:
        return JsonResponse({'ok': False, 'message': '처리 중입니다. 잠시 후 같은 내용으로 다시 눌러 주세요.'}, status=409)
    return JsonResponse({'ok': True, 'slip': serialize(slip)})


@never_cache
@require_GET
def oddsportal(request):
    from .models import OddsPortalSnapshot
    state=OddsPortalSnapshot.objects.filter(pk=1).first()
    if not state or not state.fetched_at:
        return JsonResponse({"ok":False,"message":"OddsPortal 수집 데이터가 아직 없습니다."},status=503)
    scope=request.GET.get('scope','active')
    if scope not in ('active','results','all'):
        return JsonResponse({'ok':False,'message':'올바르지 않은 경기 목록입니다.'},status=400)
    from catalog.odds import apply_prices, categorize
    items=categorize(apply_prices(state.payload.get('items',[]), 'oddsportal'), 'oddsportal')
    finished=[item for item in items if item.get('status')=='finished']
    active=[item for item in items if item.get('status') not in ('finished','cancelled')]
    selected=items if scope=='all' else finished if scope=='results' else active
    return JsonResponse({"ok":True,**state.payload,"items":selected,"scope":scope,
                         "activeCount":len(active),"resultCount":len(finished),
                         "fetchedAt":state.fetched_at.isoformat(),"error":state.last_error})
