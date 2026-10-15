"""Read the public result feed used by the official NTRY embed; settle simulations only."""
import json
from datetime import date, datetime, time, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import DemoLeg, PowerballResult, PowerballSync
from .powerball import KST
from .settlement import settle

RESULT_URL = 'https://ntry.com/data/json/games/powerball/recent_result.json'


def read_results():
    with urlopen(Request(RESULT_URL, headers={'User-Agent':'EvePreview-ResultSync/1.0','Accept':'application/json'}), timeout=15) as response:
        raw=response.read(300001)
    if len(raw)>300000: raise ValueError('결과 응답 크기가 한도를 초과했습니다.')
    data=json.loads(raw)
    if not isinstance(data,list) or not 1<=len(data)<=300: raise ValueError('공식 결과 형식이 올바르지 않습니다.')
    return data


def integer(value, low, high):
    if isinstance(value,bool) or not isinstance(value,(str,int)) or not str(value).isdigit(): raise ValueError('결과 숫자 형식이 올바르지 않습니다.')
    number=int(value)
    if not low<=number<=high: raise ValueError('결과 숫자 범위를 벗어났습니다.')
    return number


def validate_result(raw):
    if not isinstance(raw,dict): raise ValueError('결과 항목 형식이 올바르지 않습니다.')
    day=date.fromisoformat(raw['reg_date'])
    round_number=integer(raw['date_round'],1,288)
    balls=[integer(raw[f'ball_{i}'],1,28) for i in range(1,6)]
    if len(set(balls))!=5: raise ValueError('일반볼 숫자가 중복되었습니다.')
    power=integer(raw['powerball'],0,9)
    global_round=integer(raw['round'],1,100000000000)
    draw=datetime.combine(day,time(0,4,35),tzinfo=KST)+timedelta(minutes=5*(round_number-1))
    if draw>timezone.now(): raise ValueError('아직 추첨되지 않은 회차입니다.')
    return {'day':day,'round_number':round_number,'global_round':global_round,'balls':balls,'powerball':power}


@transaction.atomic
def save_results(items):
    normalized=[validate_result(raw) for raw in items]
    seen=set()
    for item in normalized:
        key=(item['day'],item['round_number'])
        if key in seen: raise ValueError('결과 회차가 중복되었습니다.')
        seen.add(key)
        old=PowerballResult.objects.filter(day=item['day'],round_number=item['round_number']).first()
        if old and any(getattr(old,key)!=item[key] for key in ('global_round','balls','powerball')):
            raise ValueError('이미 저장한 공식 결과와 다른 값이 감지되어 자동 처리를 중단했습니다.')
        if not old:
            if PowerballResult.objects.filter(global_round=item['global_round']).exists(): raise ValueError('전체 회차 식별자가 충돌합니다.')
            PowerballResult.objects.create(**item)
    return len(normalized)


def result_for(selection, result):
    from .powerball_outcomes import outcomes
    winners=outcomes(result)
    market=selection.get('market')
    if market not in winners: raise ValueError('지원하지 않는 파워볼 선택 항목입니다.')
    return 'won' if selection.get('name')==winners[market] else 'lost'


def operator_account():
    User=get_user_model()
    user,created=User.objects.get_or_create(username='ntry_result_worker', defaults={'nickname':'파워볼 자동 정산','is_staff':True,'account_status':'approved'})
    if created:
        user.set_unusable_password(); user.save(update_fields=['password'])
        user.user_permissions.add(Permission.objects.get(content_type__app_label='sportsfeed',codename='change_demoslip'))
    if user.has_usable_password() or not user.is_active or not user.is_staff:
        raise ValueError('자동 정산 전용 계정 설정을 확인해 주세요.')
    return user


def apply_pending():
    pending=DemoLeg.objects.filter(slip__source='powerball',result='pending').select_related('slip')
    count=0; actor=None
    for leg in pending.iterator():
        try:
            prefix,day,number=leg.selection['eventId'].split(':')
            if prefix!='powerball': raise ValueError('회차 식별자가 올바르지 않습니다.')
            result=PowerballResult.objects.filter(day=date.fromisoformat(day),round_number=integer(number,1,288)).first()
            if result is None: continue
            if actor is None: actor=operator_account()
            count+=settle(leg.slip_id,actor,result=result_for(leg.selection,result),position=leg.position)
        except (KeyError,TypeError): raise ValueError('저장된 선택 정보를 확인해 주세요.')
    return count


def sync_results(force=False):
    state,_=PowerballSync.objects.get_or_create(pk=1)
    if not state.enabled: return {'disabled':True,'results':0,'settled':0}
    if state.fetched_at and timezone.now()-state.fetched_at<timedelta(seconds=25) and not force:
        return {'cached':True,'results':0,'settled':apply_pending()}
    acquired=PowerballSync.objects.filter(pk=1,enabled=True).filter(Q(syncing=False)|Q(started_at__lt=timezone.now()-timedelta(minutes=2))).update(syncing=True,started_at=timezone.now())
    if not acquired: return {'busy':True,'results':0,'settled':0}
    try:
        count=save_results(read_results())
        settled=apply_pending()
        PowerballSync.objects.filter(pk=1).update(fetched_at=timezone.now(),last_error='')
        return {'results':count,'settled':settled}
    except (HTTPError,URLError,TimeoutError,OSError,json.JSONDecodeError,ValueError,TypeError,KeyError,ValidationError) as exc:
        message=exc.messages[0] if isinstance(exc,ValidationError) else str(exc)
        PowerballSync.objects.filter(pk=1).update(last_error=message[:500])
        raise ValueError('파워볼 결과 조회·정산을 완료하지 못했습니다: '+message) from exc
    finally:
        PowerballSync.objects.filter(pk=1).update(syncing=False)
