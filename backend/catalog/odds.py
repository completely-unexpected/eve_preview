"""Manual prices are an overlay; source snapshots and accepted slips stay intact."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from .models import ManualOdds

SPORT_NAMES = {'football':'축구', 'soccer':'축구', 'baseball':'야구', 'basketball':'농구', 'tennis':'테니스', 'ice-hockey':'아이스하키', 'volleyball':'배구', 'handball':'핸드볼', 'table-tennis':'탁구', 'badminton':'배드민턴', 'cricket':'크리켓', 'boxing':'권투', 'mma':'MMA', 'mixed-martial-arts':'MMA', 'american-football':'미식축구', 'rugby-league':'럭비', 'rugby-union':'럭비 유니온', 'snooker':'스누커', 'darts':'다트', 'aussie-rules':'호주식 축구', 'futsal':'풋살', 'floorball':'플로어볼', 'esports':'E스포츠', 'powerball':'파워볼'}


def categorize(items, source):
    from urllib.parse import urlsplit
    last_league = {}
    result = deepcopy(items)
    for event in result:
        if source == 'oddsportal':
            path = urlsplit(event.get('url', '')).path.strip('/').split('/')
            sport = path[0] if len(path) > 1 and path[1] == 'h2h' else event.get('sport', 'other').lower().replace(' ', '-')
            raw = event.get('leagueText', '')
            parts = [part.strip() for part in raw.split('/')]
            if len(parts) >= 3 and all(parts[:3]):
                last_league[sport] = ' / '.join(parts[1:])
            league = event.get('league') or last_league.get(sport) or '리그 미확인'
            event['league'] = league
            event['leagueKey'] = hashlib.sha256((sport+':'+league).encode()).hexdigest()[:24]
        elif source in ('harvester','inplay'):
            sport = event.get('sport','other')
        else:
            sport = 'powerball' if source == 'powerball' else str(event.get('group') or event.get('sport') or 'other').lower().replace(' ', '-')
        if sport == 'soccer': sport = 'football'
        event['sportKey'] = sport
        event['sportLabel'] = SPORT_NAMES.get(sport, event.get('group') or event.get('sport') or '기타')
    from .league_names import localize_events
    return localize_events(result)


def finished(event):
    return bool(event.get('completed')) or event.get('status') in ('finished', 'completed', 'cancelled', 'void')


def display_price(value):
    try:
        number = Decimal(str(value))
        return format(number, '.2f') if number.is_finite() else '—'
    except Exception:
        return '—'


def choices(event, source):
    if source == 'oddsportal':
        for index, value in enumerate(event.get('odds', [])):
            yield str(index), f'표시 배당 {index + 1}', value, event['odds'], index
        return
    for book in event.get('bookmakers', []):
        for market in book.get('markets', []):
            for outcome in market.get('outcomes', []):
                identity = [book.get('key'), market.get('key'), outcome.get('name'), outcome.get('point'), outcome.get('description', '')]
                key = hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode()).hexdigest()
                label = ' / '.join(str(v) for v in [book.get('title', book.get('key')), market.get('title', market.get('key')), outcome.get('name'), outcome.get('point')] if v is not None)
                yield key, label, outcome.get('price'), outcome, 'price'


def apply_prices(items, source):
    result = deepcopy(items)
    overrides = {row.event_id: row.prices for row in ManualOdds.objects.filter(source=source, event_id__in=[str(item['id']) for item in result])}
    for event in result:
        for key, label, value, container, index in choices(event, source):
            price = overrides.get(str(event['id']), {}).get(key)
            if price is not None:
                container[index] = format(Decimal(price), '.4f')
    return result


def row_display(event, source):
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone
    from zoneinfo import ZoneInfo
    start = parse_datetime(event.get('startsAt', ''))
    time = timezone.localtime(start, ZoneInfo('Asia/Seoul')).strftime('%m-%d %H:%M') if start and timezone.is_aware(start) else event.get('statusText', '—')
    home, away, middle = '—', '—', 'VS'
    if source == 'oddsportal':
        odds = event.get('odds', [])
        home = odds[0] if odds else '—'
        away = odds[-1] if len(odds) > 1 else '—'
        if len(odds) == 3: middle = display_price(odds[1])
    else:
        book = next(iter(event.get('bookmakers', [])), {})
        market = next((m for m in book.get('markets', []) if m.get('key') == 'h2h'), None)
        market = market or next((m for m in book.get('markets', []) if m.get('key') == 'spreads'), None)
        market = market or next((m for m in book.get('markets', []) if m.get('key') == 'portal_display'), None)
        if market and market.get('key') == 'portal_display':
            displayed=event.get('raw',{}).get('odds',[])
            home=displayed[0] if displayed else '—'
            away=displayed[-1] if len(displayed)>1 else '—'
            if len(displayed)==3: middle=display_price(displayed[1])
        for outcome in market.get('outcomes', []) if market else []:
            if outcome.get('name') == event.get('home'):
                home = outcome.get('price', '—')
                if outcome.get('point') is not None: middle = outcome['point']
            elif outcome.get('name') == event.get('away'): away = outcome.get('price', '—')
            elif outcome.get('name') == 'Draw': middle = display_price(outcome.get('price', '—'))
    scores = event.get('scores')
    score = ' : '.join(str(s.get('score', '—')) if isinstance(s, dict) else str(s) for s in scores) if scores else '—'
    winner = ''
    if finished(event) and source != 'powerball' and scores and len(scores) == 2:
        try:
            if all(isinstance(s, dict) for s in scores):
                mapped = {s.get('name'): Decimal(str(s['score'])) for s in scores}
                home_score, away_score = mapped[event['home']], mapped[event['away']]
            else:
                home_score, away_score = [Decimal(str(s)) for s in scores]
            if home_score.is_finite() and away_score.is_finite():
                winner = 'home' if home_score > away_score else 'away' if away_score > home_score else ''
        except (ValueError, KeyError, TypeError, ArithmeticError):
            pass
    home_key = away_key = middle_key = ''
    if source == 'oddsportal':
        home_key = '0' if event.get('odds') else ''
        away_key = str(len(event['odds'])-1) if len(event.get('odds', [])) > 1 else ''
        middle_key = '1' if len(event.get('odds', [])) == 3 else ''
    elif market:
        for key, label, value, container, index in choices(event, source):
            if any(container is outcome for outcome in market.get('outcomes', [])):
                if market.get('key') == 'portal_display':
                    column=container.get('displayColumn')
                    count=len(event.get('raw',{}).get('odds',[]))
                    if column==0: home_key=key
                    elif column==count-1: away_key=key
                    elif count==3 and column==1: middle_key=key
                if container.get('name') == event.get('home'): home_key = key
                elif container.get('name') == event.get('away'): away_key = key
                elif container.get('name') == 'Draw': middle_key = key
    return {'time': time, 'home_price': display_price(home), 'away_price': display_price(away), 'middle': middle, 'score': score,
            'home_key': home_key, 'away_key': away_key, 'middle_key': middle_key, 'winner': winner}


def managed_events():
    from sportsfeed.models import FeedSnapshot, OddsPortalSnapshot, PowerballResult, HarvesterSnapshot, InplaySnapshot
    from sportsfeed.powerball import current_board
    from .models import Game
    rows = []
    for source, label, model in [('sports', '스포츠', FeedSnapshot), ('oddsportal', 'OddsPortal', OddsPortalSnapshot), ('harvester','OddsHarvester',HarvesterSnapshot),('inplay','Inplay',InplaySnapshot)]:
        state = model.objects.filter(pk=1).first()
        for event in categorize(state.payload.get('items', []), source) if state else []:
            rows.append({'source': source, 'source_label': label, 'event': event})
    if Game.objects.filter(slug='powerball', is_published=True).exists():
        rows.extend({'source': 'powerball', 'source_label': '엔트리 파워볼', 'event': event} for event in current_board(manual=False)['items'])
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo
    from sportsfeed.powerball_outcomes import outcomes
    for result in PowerballResult.objects.all():
        draw = datetime.combine(result.day, time(0, 4, 35), tzinfo=ZoneInfo('Asia/Seoul')) + timedelta(minutes=5*(result.round_number-1))
        event = current_board(now=draw-timedelta(seconds=60), manual=False)['items'][0]
        event.update(completed=True, status='finished', scores=[*result.balls, result.powerball],
            powerballResult={'day':result.day,'round':result.round_number,'balls':result.balls,'total':sum(result.balls),'powerball':result.powerball,**outcomes(result)})
        rows.append({'source':'powerball', 'source_label':'엔트리 파워볼', 'event':event})
    for row in rows:
        if row['source'] == 'powerball': row['event'].update(sportKey='powerball', sportLabel='파워볼')
    return rows
