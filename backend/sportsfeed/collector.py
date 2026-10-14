from datetime import datetime, timezone as dt_timezone, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone
from .models import FeedSnapshot
from .services import ProviderError, request_json


def normalize_event(item, league):
    try:
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key] for key in ("id", "home_team", "away_team")):
            return None
        start = datetime.fromisoformat(item["commence_time"].replace("Z", "+00:00"))
        if start.tzinfo is None: return None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
    return {
        "id": item["id"][:100], "home": item["home_team"][:200], "away": item["away_team"][:200],
        "startsAt": start.astimezone(dt_timezone.utc).isoformat(), "leagueKey": league["key"],
        "league": league["title"], "group": league["group"], "bookmakers": [], "scores": None,
        "completed": False, "status": "scheduled" if start > timezone.now() else "unconfirmed",
    }


def normalize_books(items):
    result = []
    for book in items if isinstance(items, list) else []:
        if not isinstance(book, dict) or not isinstance(book.get("key"), str): continue
        markets = []
        for market in book.get("markets", []):
            if not isinstance(market, dict) or not isinstance(market.get("key"), str): continue
            outcomes = []
            for outcome in market.get("outcomes", []):
                if not isinstance(outcome, dict) or not isinstance(outcome.get("name"), str): continue
                try:
                    price = Decimal(str(outcome.get("price")))
                    if not price.is_finite() or not 1 < price <= 1000000: continue
                    price = str(price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
                    point = outcome.get("point")
                    if point is not None:
                        point = Decimal(str(point))
                        if not point.is_finite(): continue
                        point = str(point.normalize())
                except (InvalidOperation, ValueError, TypeError): continue
                outcomes.append({"name": outcome["name"][:200], "price": price, "point": point, "description": str(outcome.get("description", ""))[:200]})
            if outcomes: markets.append({"key": market["key"][:100], "updatedAt": str(market.get("last_update", ""))[:40], "outcomes": outcomes})
        if markets:
            result.append({"key": book["key"][:100], "title": str(book.get("title", book["key"]))[:200], "markets": markets})
    result.sort(key=lambda book: (book["key"] != "pinnacle", book["key"] != "betfair_ex_eu", book["title"]))
    return result


def collect(force=False, progress=None):
    snapshot, _ = FeedSnapshot.objects.get_or_create(pk=1)
    if snapshot.fetched_at and not force and snapshot.payload.get("complete"):
        return snapshot
    acquired = FeedSnapshot.objects.filter(pk=1).filter(Q(syncing=False) | Q(started_at__lt=timezone.now() - timedelta(minutes=30))).update(syncing=True, started_at=timezone.now(), last_error="")
    if not acquired: raise ProviderError("이미 전체 경기를 조회하고 있습니다.")
    payload = snapshot.payload if snapshot.payload and not force and not snapshot.payload.get("complete") else {}
    try:
        catalog, usage = request_json("sports/")
        leagues = [{"key": item["key"], "title": item.get("title", item["key"]), "group": item.get("group", "기타")}
                   for item in catalog if isinstance(item, dict) and item.get("active") and not item.get("has_outrights")]
        leagues.sort(key=lambda item: (item["group"] != "Soccer", item["title"]))
        available = usage.get("remaining")
        if force and snapshot.payload.get("complete") and available is not None and available < len(leagues) * 4:
            raise ProviderError(f"전체 재조회에는 최대 {len(leagues) * 4}크레딧이 필요합니다. 남은 {available}크레딧으로는 부족하여 기존 데이터를 유지합니다.")

        events = {event["id"]: event for event in payload.get("items", [])}
        done = set(payload.get("completedLeagues", []))
        errors = list(payload.get("errors", []))
        score_errors = list(payload.get("scoreErrors", []))
        remaining = usage.get("remaining")
        initial_remaining = remaining
        for index, league in enumerate(leagues, 1):
            key = league["key"]
            if key in done: continue
            if remaining is not None and remaining < 4:
                errors.append({"league": key, "message": "남은 크레딧이 부족해 추가 조회를 중지했습니다."})
                break
            if progress: progress(f"{index}/{len(leagues)} {key}")
            try:
                scheduled, _ = request_json("sports/" + key + "/events")
                local = {}
                for item in scheduled:
                    event = normalize_event(item, league)
                    if event: local[event["id"]] = event
                odds, odds_usage = request_json("sports/" + key + "/odds", {"regions": "eu", "markets": "h2h,spreads,totals", "oddsFormat": "decimal"})
                remaining = odds_usage.get("remaining", remaining)
                for item in odds:
                    event = normalize_event(item, league)
                    if event:
                        event["bookmakers"] = normalize_books(item.get("bookmakers", []))
                        local[event["id"]] = event
                try:
                    scores, score_usage = request_json("sports/" + key + "/scores")
                    remaining = score_usage.get("remaining", remaining)
                    for item in scores:
                        if not isinstance(item, dict) or item.get("id") not in local: continue
                        event = local[item["id"]]
                        event["completed"] = item.get("completed") is True
                        score = item.get("scores")
                        if isinstance(score, list):
                            event["scores"] = [{"name": str(row.get("name", ""))[:200], "score": str(row.get("score", ""))[:30]} for row in score if isinstance(row, dict)]
                        event["status"] = "completed" if event["completed"] else "live" if event["scores"] and event["startsAt"] <= timezone.now().isoformat() else event["status"]
                except ProviderError:
                    score_errors.append(key)
                events.update(local)
                done.add(key)
            except ProviderError as exc:
                errors.append({"league": key, "message": str(exc)})
                break
            payload = {"items": sorted(events.values(), key=lambda event: event["startsAt"]), "leagues": leagues, "completedLeagues": sorted(done), "errors": errors, "scoreErrors": score_errors, "remainingCredits": remaining, "initialCredits": initial_remaining, "complete": len(done) == len(leagues), "source": "The Odds API", "regions": "eu", "markets": ["h2h", "spreads", "totals"]}
            FeedSnapshot.objects.filter(pk=1).update(payload=payload, fetched_at=timezone.now())
        payload.update({"items": sorted(events.values(), key=lambda event: event["startsAt"]), "leagues": leagues, "completedLeagues": sorted(done), "errors": errors, "scoreErrors": score_errors, "remainingCredits": remaining, "complete": len(done) == len(leagues), "source": "The Odds API"})
        FeedSnapshot.objects.filter(pk=1).update(payload=payload, fetched_at=timezone.now(), last_error=errors[-1]["message"] if errors else "")
        snapshot.refresh_from_db()
        return snapshot
    finally:
        FeedSnapshot.objects.filter(pk=1).update(syncing=False)
        snapshot.syncing = False
