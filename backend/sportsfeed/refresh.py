"""Budgeted soccer refresh preserving other sports and accepted quote snapshots."""
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import FeedSnapshot
from .collector import normalize_books, normalize_event
from .services import ProviderError, request_json


def refresh_soccer(progress=None):
    snapshot, _ = FeedSnapshot.objects.get_or_create(pk=1)
    acquired = FeedSnapshot.objects.filter(pk=1).filter(Q(syncing=False) | Q(started_at__lt=timezone.now()-timedelta(minutes=30))).update(syncing=True, started_at=timezone.now(), last_error='')
    if not acquired: raise ProviderError('이미 경기를 갱신하고 있습니다.')
    try:
        catalog, usage = request_json('sports/')
        leagues = [{'key': x['key'], 'title': x.get('title', x['key']), 'group': x.get('group', '')} for x in catalog if x.get('active') and not x.get('has_outrights')]
        old = snapshot.payload or {}
        items = {e['id']: e for e in old.get('items', [])}
        now = timezone.now()
        recent = {e['leagueKey'] for e in items.values() if e.get('group') == 'Soccer' and not e.get('completed') and now-timedelta(days=1) <= parse_datetime(e['startsAt']) <= now}
        soccer = [x for x in leagues if x['group'] == 'Soccer']
        soccer.sort(key=lambda x: (x['key'] not in recent, x['key'] != 'soccer_epl', x['key']))
        remaining = usage.get('remaining')
        if remaining is None or remaining < len(soccer)*3:
            raise ProviderError('모든 축구 리그의 기본 배당을 갱신할 크레딧이 부족합니다. 기존 데이터를 유지합니다.')
        updated = dict(old.get('leagueUpdatedAt', {}))
        refreshed, score_refreshed, errors = [], [], []
        base_remaining = remaining
        for index, league in enumerate(soccer):
            key = league['key']
            if remaining < 3:
                errors.append({'league': key, 'message': '남은 크레딧 부족'})
                break
            if progress: progress(f'{index+1}/{len(soccer)} {key} · remaining {remaining}')
            try:
                scheduled, _ = request_json('sports/'+key+'/events')
                odds, usage = request_json('sports/'+key+'/odds', {'regions': 'eu', 'markets': 'h2h,spreads,totals', 'oddsFormat': 'decimal'})
                remaining = usage.get('remaining', remaining-3)
                local = {}
                for raw in scheduled:
                    event = normalize_event(raw, league)
                    if event: local[event['id']] = event
                for raw in odds:
                    event = normalize_event(raw, league)
                    if event:
                        event['bookmakers'] = normalize_books(raw.get('bookmakers', []))
                        local[event['id']] = event
                # Future fixtures missing from the fresh provider response are no longer offered.
                items = {eid: e for eid, e in items.items() if e.get('leagueKey') != key or parse_datetime(e['startsAt']) <= now}
                for event_id,event in local.items():
                    previous=items.get(event_id)
                    items[event_id]=previous if previous and previous.get('completed') and previous.get('resultSource') else event
                reserve = 3*(len(soccer)-index-1)
                if key in recent and remaining >= reserve+2:
                    try:
                        scores, score_usage = request_json('sports/'+key+'/scores', {'daysFrom': 1})
                        remaining = score_usage.get('remaining', remaining-2)
                        for raw in scores:
                            event = items.get(raw.get('id'))
                            if not event or event.get('leagueKey') != key: continue
                            event['completed'] = raw.get('completed') is True
                            rows = raw.get('scores')
                            event['scores'] = [{'name': str(r.get('name', ''))[:200], 'score': str(r.get('score', ''))[:30]} for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None
                            event['status'] = 'completed' if event['completed'] else 'live' if event['scores'] and parse_datetime(event['startsAt']) <= now else 'scheduled' if parse_datetime(event['startsAt']) > now else 'unconfirmed'
                        score_refreshed.append(key)
                    except ProviderError as exc:
                        errors.append({'league': key, 'message': '결과 조회: '+str(exc)})
                updated[key] = timezone.now().isoformat()
                refreshed.append(key)
            except ProviderError as exc:
                errors.append({'league': key, 'message': str(exc)})
            payload = {**old, 'items': sorted(items.values(), key=lambda e:e['startsAt']), 'leagues': leagues,
                       'leagueUpdatedAt': updated, 'completedLeagues': sorted(set(old.get('completedLeagues', [])) | set(refreshed)), 'remainingCredits': remaining,
                       'lastRefresh': {'group': 'Soccer', 'leagues': refreshed, 'scoreLeagues': score_refreshed, 'errors': errors, 'spent': base_remaining-remaining}}
            FeedSnapshot.objects.filter(pk=1).update(payload=payload, fetched_at=timezone.now())
        snapshot.refresh_from_db()
        return snapshot
    finally:
        FeedSnapshot.objects.filter(pk=1).update(syncing=False)
