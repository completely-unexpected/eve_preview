import re
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from .models import FeedSnapshot
from .services import ProviderError, request_json
from .collector import normalize_books


def load_extra(event_id, operator):
    if not operator.is_active or not operator.is_staff or not operator.has_perm("sportsfeed.change_feedsnapshot"):
        raise PermissionError("세부 배당 조회는 관리자만 사용할 수 있습니다.")
    if not isinstance(event_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", event_id):
        raise ValueError("경기 번호가 올바르지 않습니다.")
    snapshot = FeedSnapshot.objects.filter(pk=1).first()
    if snapshot is None: raise ProviderError("전체 경기 목록을 먼저 조회해 주세요.")
    event = next((item for item in snapshot.payload.get("items", []) if item["id"] == event_id), None)
    if event is None: raise ValueError("저장된 경기 목록에 없는 경기입니다.")
    previous = event.get("extraMarkets", {}).get("fetchedAt")
    if previous and timezone.now() - timezone.datetime.fromisoformat(previous) < timedelta(minutes=5):
        return event, snapshot.payload.get("remainingCredits")
    acquired = FeedSnapshot.objects.filter(pk=1).filter(Q(syncing=False) | Q(started_at__lt=timezone.now() - timedelta(minutes=30))).update(syncing=True, started_at=timezone.now())
    if not acquired: raise ProviderError("다른 배당 조회가 진행 중입니다. 잠시 후 다시 시도해 주세요.")
    try:
        path = "sports/" + event["leagueKey"] + "/events/" + event_id
        catalog, usage = request_json(path + "/markets", {"regions": "eu"}, object_response=True)
        keys = sorted({market["key"] for book in catalog.get("bookmakers", []) for market in book.get("markets", []) if isinstance(market, dict) and isinstance(market.get("key"), str) and re.fullmatch(r"[a-z0-9_]{1,100}", market["key"])})
        remaining = usage.get("remaining")
        allowance = remaining if remaining is not None else snapshot.payload.get("remainingCredits", 0)
        requested = keys[:max(0, min(100, allowance or 0))]
        if keys and not requested: raise ProviderError("남은 크레딧이 부족해 세부 배당을 조회할 수 없습니다.")
        if requested:
            response, usage = request_json(path + "/odds", {"regions": "eu", "markets": ",".join(requested), "oddsFormat": "decimal"}, object_response=True)
            if response.get("id") != event_id: raise ProviderError("요청한 경기와 응답 경기 번호가 다릅니다.")
            event["bookmakers"] = normalize_books(response.get("bookmakers", []))
            remaining = usage.get("remaining", remaining)
        event["extraMarkets"] = {"fetchedAt": timezone.now().isoformat(), "complete": len(requested) == len(keys), "availableCount": len(keys), "requestedCount": len(requested)}
        snapshot.payload["remainingCredits"] = remaining
        FeedSnapshot.objects.filter(pk=1).update(payload=snapshot.payload)
        return event, remaining
    finally:
        FeedSnapshot.objects.filter(pk=1).update(syncing=False)
