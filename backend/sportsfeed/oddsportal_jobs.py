import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import OddsPortalCollectionJob as Job, OddsPortalSnapshot
from .collector_control import set_paused


def expire_stale():
    Job.objects.filter(active_key='today', updated_at__lt=timezone.now()-timedelta(minutes=15)).update(
        status=Job.Status.FAILED, error='수집 프로세스의 진행 응답이 끊겼습니다. 다시 실행해 주세요.', active_key=None, finished_at=timezone.now())


def launch_job(job):
    options = {'cwd': str(settings.BASE_DIR.parent), 'stdin': subprocess.DEVNULL,
               'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL, 'close_fds': True,
               'env': {**os.environ, 'EVEPREVIEW_JOB_DATABASE': str(settings.DATABASES['default']['NAME'])}}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    subprocess.Popen([sys.executable, str(settings.BASE_DIR/'manage.py'), 'collect_oddsportal_today', str(job.pk)], **options)


def start_job(user,options=None):
    expire_stale()
    try:
        with transaction.atomic():
            job=Job.objects.create(requested_by=user, day=timezone.now().astimezone(ZoneInfo('Asia/Seoul')).date(),options=options or {})
    except IntegrityError:
        return Job.objects.get(active_key='today'), False
    try:
        launch_job(job)
    except OSError as exc:
        Job.objects.filter(pk=job.pk).update(status=Job.Status.FAILED, error=str(exc)[:500], active_key=None, finished_at=timezone.now())
        job.refresh_from_db()
    return job, True


@transaction.atomic
def merge_page(items, day, zone):
    state,_=OddsPortalSnapshot.objects.get_or_create(pk=1)
    state=OddsPortalSnapshot.objects.select_for_update().get(pk=state.pk)
    old={item['id']:item for item in state.payload.get('items', [])}
    for item in items:
        if not all(isinstance(item.get(key),str) and item[key] for key in ('id','home','away','url')):
            raise ValueError('경기 식별 정보가 올바르지 않습니다.')
        previous=old.get(item['id'])
        if previous and (previous['home']!=item['home'] or previous['away']!=item['away']):
            raise ValueError('동일 경기 ID의 팀 정보가 충돌했습니다.')
        if previous and previous.get('status')=='finished' and item.get('status')!='finished':
            continue
        old.pop(item['id'],None)
        old[item['id']]=item
    state.payload={**state.payload, 'source':'OddsPortal', 'timezone':zone,
                   'collectionDay':day, 'items':list(old.values())[-20000:],
                   'oddsLabel':'OddsPortal displayed odds; bookmaker not identified'}
    state.fetched_at=timezone.now()
    state.last_error=''
    state.save()


def serialize(job):
    return {'id':job.pk, 'status':job.status, 'statusLabel':job.get_status_display(), 'day':str(job.day),
            'currentSport':job.current_sport, 'done':job.pages_done, 'total':job.pages_total,
            'count':job.match_count, 'reports':job.reports, 'error':job.error,
            'active':job.active_key is not None, 'updatedAt':job.updated_at.isoformat()}


def run_job(job_id):
    if not Job.objects.filter(pk=job_id,status=Job.Status.QUEUED,active_key='today').update(status=Job.Status.RUNNING,updated_at=timezone.now()):
        return
    job=Job.objects.get(pk=job_id)
    node=shutil.which('node') or str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'nodejs/node.exe')
    process=None
    ids=set()
    try:
        set_paused(False)
        options={'stdout':subprocess.PIPE,'stderr':subprocess.DEVNULL,'text':True,'encoding':'utf-8','cwd':str(settings.BASE_DIR.parent),'env':{**os.environ,'ODDSPORTAL_SPORT':job.options.get('sport','all')}}
        if os.name=='nt': options['creationflags']=subprocess.CREATE_NO_WINDOW
        process=subprocess.Popen([node,str(settings.BASE_DIR.parent/'tools/oddsportal/today.cjs')],**options)
        completed=False
        for line in process.stdout:
            event=json.loads(line)
            if not Job.objects.filter(pk=job.pk,active_key='today').exists():
                raise ValueError('수집 작업이 만료되었습니다.')
            kind=event.get('type')
            if kind=='fatal': raise ValueError(event.get('error','수집 실패'))
            if kind in ('discovery','progress'): job.current_sport=event.get('sport','')[:100]
            if kind=='plan':
                job.pages_total=event['total'];job.reports=event.get('reports',[])
            if kind=='page':
                from .parsing_options import filter_items
                limit=job.options.get('limit',0)
                selected=filter_items(event.get('items',[]),job.options,remaining=max(limit-len(ids),0) if limit else None)
                if selected:
                    merge_page(selected,event['collectionDay'],event['timezone'])
                ids.update(item['id'] for item in selected)
                job.match_count=len(ids);job.pages_done=event['completed'];job.pages_total=event['total']
                job.reports=[*job.reports,event['report']]
            if kind=='done':
                job.reports=event['reports']
                bad=[r for r in job.reports if not r.get('complete')]
                job.status=Job.Status.PARTIAL if bad else Job.Status.COMPLETE
                job.error=f'{len(bad)}개 종목에서 일부 누락 또는 오류가 있습니다.' if bad else ''
                completed=True
            job.save()
        code=process.wait(timeout=20)
        if code or not completed: raise ValueError('수집 프로세스가 완료 신호 없이 종료되었습니다.')
    except Exception as exc:
        job.status=Job.Status.PARTIAL if ids else Job.Status.FAILED
        job.error=str(exc)[:500]
    finally:
        if process and process.poll() is None: process.terminate()
        job.active_key=None;job.finished_at=timezone.now();job.save()
