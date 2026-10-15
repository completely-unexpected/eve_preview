from copy import deepcopy
from django.contrib import messages
from django.contrib.admin.models import LogEntry,CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,OperationalError
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from sportsfeed.models import FeedSnapshot,OddsPortalSnapshot,HarvesterSnapshot,HarvesterJob,OddsPortalCollectionJob,InplaySnapshot
from sportsfeed.collector_control import is_paused,set_paused
from .models import Game,ManualOdds
from .odds import finished

SOURCES=[('sports','스포츠',FeedSnapshot),('oddsportal','OddsParsing',OddsPortalSnapshot),('harvester','OddsHarvester',HarvesterSnapshot),('inplay','Inplay',InplaySnapshot)]


def counts():
    result=[]
    for source,label,model in SOURCES:
        state=model.objects.filter(pk=1).first()
        result.append({'label':label,'count':sum(not finished(event) for event in state.payload.get('items',[])) if state else 0})
    return result


def clear_matches(operator):
    if not (operator.is_active and operator.is_staff and operator.is_superuser): raise PermissionDenied
    was_paused=is_paused();set_paused(True)
    try:
        with transaction.atomic():
            total=0
            for source,label,model in SOURCES:
                state=model.objects.select_for_update().filter(pk=1).first()
                if not state: continue
                if source=='sports' and state.syncing: raise ValidationError('스포츠 API 수집이 진행 중입니다. 완료 후 다시 시도하세요.')
                payload=deepcopy(state.payload);items=payload.get('items',[])
                removed=[str(event['id']) for event in items if not finished(event)]
                payload['items']=[event for event in items if finished(event)]
                payload['lastClearedAt']=timezone.now().isoformat()
                state.payload=payload;state.save(update_fields=['payload'])
                ManualOdds.objects.filter(source=source,event_id__in=removed).delete()
                total+=len(removed)
            HarvesterJob.objects.filter(active_key='harvester').update(active_key=None,status='cancelled',error='등록 경기 전체 삭제로 수집을 중지했습니다.',finished_at=timezone.now())
            OddsPortalCollectionJob.objects.filter(active_key='today').update(active_key=None,status='failed',error='등록 경기 전체 삭제로 수집을 중지했습니다.',finished_at=timezone.now())
            LogEntry.objects.create(user=operator,content_type=ContentType.objects.get_for_model(Game),object_id='',object_repr='등록 스포츠 경기 전체 삭제',action_flag=CHANGE,change_message=f'예정·진행 경기 {total}개 삭제. 회원·배팅 내역·완료 경기 보존. 자동 웹 수집 중지.')
        return total
    except Exception:
        if not was_paused: set_paused(False)
        raise


def reset_view(model_admin,request):
    if not (request.user.is_superuser and request.user.is_active): raise PermissionDenied
    if request.method not in ('GET','POST'): return HttpResponseNotAllowed(['GET','POST'])
    if request.method=='POST':
        if request.POST.get('confirm')!='yes': messages.error(request,'삭제 확인 항목을 선택하세요.')
        else:
            try:
                count=clear_matches(request.user)
                messages.success(request,f'등록 경기 {count}개를 삭제했습니다. 다시 올라오지 않도록 자동 웹 수집을 중지했습니다.')
                return redirect('admin:catalog_game_odds')
            except (ValidationError,OperationalError) as exc:
                messages.error(request,exc.messages[0] if isinstance(exc,ValidationError) else '다른 처리가 진행 중입니다. 삭제하지 않았습니다. 잠시 후 다시 시도하세요.')
    rows=counts()
    return TemplateResponse(request,'admin/catalog/game/reset_matches.html',{**model_admin.admin_site.each_context(request),'title':'등록 스포츠 경기 전체 삭제','rows':rows,'total':sum(row['count'] for row in rows)})
