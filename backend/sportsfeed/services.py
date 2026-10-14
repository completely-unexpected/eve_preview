import json
import re
from datetime import datetime, timezone as dt_timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


class ProviderError(Exception):
    pass


def request_json(endpoint, params=None, *, object_response=False):
    if not settings.ODDS_API_KEY:
        raise ProviderError("경기 API 키가 설정되지 않았습니다. 관리자에게 문의해 주세요.")
    # Only fixed, validated paths reach this function; do not log URLs containing credentials.
    url = "https://api.the-odds-api.com/v4/" + endpoint + "?" + urlencode({**(params or {}), "apiKey": settings.ODDS_API_KEY})
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=12) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ProviderError("경기 데이터가 너무 큽니다. 잠시 후 다시 시도해 주세요.")
            data = json.loads(raw)
            if not isinstance(data, dict if object_response else list):
                raise ProviderError("경기 API의 응답 형식이 올바르지 않습니다.")
            def number(name):
                value = response.headers.get(name)
                return int(value) if isinstance(value, str) and value.isdigit() else None
            return data, {"remaining": number("x-requests-remaining"), "used": number("x-requests-used"), "cost": number("x-requests-last")}
    except HTTPError as error:
        if error.code in (401, 403):
            raise ProviderError("경기 API 인증을 확인해 주세요.") from None
        if error.code == 429:
            raise ProviderError("경기 API 요청 제한에 도달했습니다. 잠시 후 다시 시도해 주세요.") from None
        raise ProviderError("경기 제공 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.") from None
    except (URLError, TimeoutError, OSError):
        raise ProviderError("경기 제공 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.") from None
    except (ValueError, UnicodeError):
        raise ProviderError("경기 API의 응답 형식이 올바르지 않습니다.") from None


def fetch(endpoint):
    return request_json(endpoint)[0]


def leagues():
    cached = cache.get("odds-api:leagues:v1")
    if cached is not None:
        return cached
    result = []
    for item in fetch("sports/"):
        if not isinstance(item, dict) or not item.get("active") or item.get("has_outrights"):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_]{1,100}", key):
            continue
        result.append({"key": key, "title": str(item.get("title", key))[:200], "group": str(item.get("group", "기타"))[:100]})
    result.sort(key=lambda item: (item["group"], item["title"]))
    cache.set("odds-api:leagues:v1", result, 600)
    return result


def events(league):
    if not isinstance(league, str) or not re.fullmatch(r"[a-z0-9_]{1,100}", league):
        raise ValueError("조회할 리그가 올바르지 않습니다.")
    known = next((item for item in leagues() if item["key"] == league), None)
    if known is None:
        raise ValueError("현재 제공되지 않는 리그입니다.")
    cache_key = "odds-api:events:v1:" + league
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    result = []
    for item in fetch("sports/" + league + "/events"):
        if not isinstance(item, dict):
            continue
        try:
            start = datetime.fromisoformat(item["commence_time"].replace("Z", "+00:00"))
            if start.tzinfo is None or not all(isinstance(item.get(key), str) and item[key] for key in ("id", "home_team", "away_team")):
                continue
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        result.append({
            "id": item["id"][:100], "home": item["home_team"][:200], "away": item["away_team"][:200],
            "league": known["title"], "leagueKey": league, "group": known["group"],
            "startsAt": start.astimezone(dt_timezone.utc).isoformat(),
        })
    result.sort(key=lambda item: item["startsAt"])
    response = {"items": result, "fetchedAt": timezone.now().isoformat(), "source": "The Odds API", "cacheSeconds": 120}
    cache.set(cache_key, response, 120)
    return response
