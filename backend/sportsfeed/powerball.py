"""Non-redeemable simulation markets; no NTRY result feed or wagers are sent."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

KST = ZoneInfo('Asia/Seoul')
# Screenshot-derived simulation prices, not an official NTRY odds feed.
MARKETS = [
    ('general_parity', '일반볼 홀/짝', [('홀', '1.9500'), ('짝', '1.9500')]),
    ('general_range', '일반볼 구간', [('대 (81~130)', '2.8500'), ('중 (65~80)', '2.6000'), ('소 (15~64)', '2.8500')]),
    ('power_parity', '파워볼 홀/짝', [('홀', '1.9500'), ('짝', '1.9500')]),
    ('power_range', '파워볼 언더/오버', [('언더 (0~4)', '1.9500'), ('오버 (5~9)', '1.9500')]),
]


def current_board(now=None, *, manual=True):
    now = now or timezone.now()
    local = now.astimezone(KST)
    first = datetime.combine(local.date(), time(0, 4, 35), tzinfo=KST)
    offset = max(0, int((local-first).total_seconds() // 300) + 1) if local >= first else 0
    draw = first + timedelta(minutes=5*offset)
    rounds = []
    for i in range(3):
        starts = draw + timedelta(minutes=5*i)
        round_number = (starts.hour*60+starts.minute)//5+1
        closes = starts-timedelta(seconds=30)
        day = starts.date().isoformat()
        rounds.append({'id': f'powerball:{day}:{round_number}', 'day': day, 'round': round_number,
                       'home': '엔트리 파워볼', 'away': f'{round_number}회차', 'league': '엔트리 5분 파워볼',
                       'startsAt': starts.isoformat(), 'closesAt': closes.isoformat(), 'completed': False,
                       'status': 'scheduled', 'bookmakers': [{'key': 'simulation', 'title': '기본 배당',
                        'markets': [{'key': key, 'title': title, 'outcomes': [{'name': name, 'price': price, 'point': None, 'description': ''} for name,price in outcomes]}
                                    for key,title,outcomes in MARKETS]}]})
    from catalog.odds import apply_prices
    return {'ok': True, 'serverTime': now.isoformat(), 'items': apply_prices(rounds, 'powerball') if manual else rounds, 'cutoffSeconds': 30, 'virtualOnly': True}


@never_cache
@require_GET
def board(request):
    from catalog.models import Game
    if not Game.objects.filter(slug='powerball', is_published=True).exists():
        return JsonResponse({'ok': False, 'message': '현재 운영하지 않는 게임입니다.'}, status=404)
    from .models import PowerballResult, PowerballSync
    state=PowerballSync.objects.filter(pk=1).first()
    payload=current_board()
    from .powerball_outcomes import outcomes
    payload['results']=[{'day':r.day.isoformat(),'round':r.round_number,'balls':r.balls,'total':sum(r.balls),'powerball':r.powerball,'outcomes':outcomes(r)} for r in PowerballResult.objects.all()[:12]]
    payload['resultSync']={'enabled':bool(state and state.enabled),'fetchedAt':state.fetched_at.isoformat() if state and state.fetched_at else None,'error':state.last_error if state else ''}
    return JsonResponse(payload)
