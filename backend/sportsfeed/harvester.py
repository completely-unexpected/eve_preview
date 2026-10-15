"""An isolated OddsHarvester adapter; never writes the existing feed snapshots."""
from copy import deepcopy
from datetime import datetime, UTC, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django import forms
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import HarvesterJob as Job, HarvesterSnapshot, InplaySnapshot

SPORTS = [('football','축구'),('baseball','야구'),('basketball','농구'),('tennis','테니스'),('ice-hockey','아이스하키'),('volleyball','배구'),('american-football','미식축구'),('handball','핸드볼'),('rugby-league','럭비 리그'),('rugby-union','럭비 유니온'),('cricket','크리켓')]
WINNER = {'football':'1x2','tennis':'match_winner','baseball':'home_away','basketball':'home_away','american-football':'home_away','ice-hockey':'1x2','volleyball':'home_away','handball':'1x2','rugby-league':'1x2','rugby-union':'1x2','cricket':'home_away'}
ROOT = settings.BASE_DIR.parent
CATALOG=json.loads((ROOT/'tools/harvester/supported.json').read_text(encoding='utf-8'))
LEAGUES={urlsplit(url).path.strip('/'):slug for leagues in CATALOG['leagues'].values() for slug,url in leagues.items()}


def markets_for(sport,scope):
    if scope=='all': return ','.join(CATALOG['markets'].get(sport,[WINNER[sport]]))
    return WINNER[sport]+(',over_under'+('' if sport=='baseball' else ',asian_handicap') if scope=='main' and sport in ('football','baseball','basketball','ice-hockey','american-football') else '')


def plans_for(job):
    sports=[key for key,_ in SPORTS] if job.sport=='all' else [job.sport]
    modes=['upcoming','historic'] if job.mode=='all' else [job.mode]
    for sport in sports:
        league=job.league if job.league not in ('','all') else ''
        prefix='hockey' if sport=='ice-hockey' else sport
        if league and not league.startswith((sport+'/',prefix+'/')): continue
        for mode in modes:
            leagues=','.join(sorted(key for key in LEAGUES if key.startswith((sport+'/',prefix+'/')))) if mode=='historic' and not league else league
            if mode=='historic' and not leagues: continue
            markets=markets_for(sport,job.markets) if job.markets in ('all','main','winner') else job.markets
            yield SimpleNamespace(pk=job.pk,sport=sport,mode=mode,league=leagues,markets=markets,day=job.day,limit=job.limit,starts_from=getattr(job,'starts_from',None),target_bookmaker=getattr(job,'target_bookmaker',''))


class CollectionForm(forms.Form):
    sport = forms.ChoiceField(label='종목', choices=[('all','전체'),*SPORTS],initial='football')
    mode = forms.ChoiceField(label='수집 종류', choices=[choice for choice in Job._meta.get_field('mode').choices if choice[0]!='live'])
    day = forms.DateTimeField(label='예정 경기 기준일시 (한국 시간)',widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local'}),input_formats=['%Y-%m-%dT%H:%M','%Y-%m-%d'],initial=lambda:timezone.now().astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%dT%H:%M'),help_text='선택 날짜에서 이 시각 이후에 시작하는 예정 경기를 수집합니다. 리그를 지정해도 이 기준을 적용합니다.')
    league = forms.ChoiceField(label='리그',required=False,choices=[('all','전체'),*[(key,key) for key in sorted(LEAGUES)]],help_text='전체는 해당 종목 전체 리그입니다. 과거 결과에서는 지원 리그 전체입니다.')
    market_set = forms.ChoiceField(label='배당 범위', choices=[('winner','승패·승무패'),('main','승패·승무패 + 오버언더 (지원 종목은 핸디캡 포함)'),('all','전체')])
    bookmaker = forms.ChoiceField(label='수집 업체',required=False,choices=[('','전체'),('OddsPortal (listing)','OddsPortal — 경기 목록 표시 배당'),('bet365','Bet365'),('Pinnacle','Pinnacle'),('1xBet','1xBet'),('Unibet','Unibet'),('10x10bet', '10x10bet'),('22Bet', '22Bet'),('Alphabet', 'Alphabet'),('BetInAsia', 'BetInAsia'),('Bets.io', 'Bets.io'),('bwin', 'bwin'),('Cloudbet', 'Cloudbet'),('GambleCity', 'GambleCity'),('GGBET', 'GGBET'),('Kobet', 'Kobet'),('Melbet', 'Melbet'),('Momobet', 'Momobet'),('Rainbet', 'Rainbet'),('Roobet', 'Roobet'),('Stake', 'Stake'),('VOBET', 'VOBET'),('custom','직접 입력')],help_text='OddsPortal 목록 옵션은 선택 날짜의 목록 표시값만 수집합니다. 리그는 전체를 선택하며 배당 범위는 적용되지 않습니다. 특정 업체의 배당이나 평균·최고 배당으로 간주하지 않습니다.')
    bookmaker_name = forms.RegexField(label='직접 입력 업체명',regex=r'^[^\x00-\x1f\x7f]+$',max_length=100,required=False,help_text='OddsPortal에 표시된 업체명을 입력하세요.')
    limit = forms.TypedChoiceField(label='최대 상세 수집 경기 수 (종목·종류별)',choices=[(10,'10'),(20,'20'),(50,'50'),(100,'100'),(0,'전체')],coerce=int,initial=10)

    def clean(self):
        data=super().clean()
        target=data.get('bookmaker','')
        if target=='custom':
            target=data.get('bookmaker_name','').strip()
            if not target: self.add_error('bookmaker_name','수집할 업체명을 입력하세요.')
        if target=='OddsPortal (listing)':
            if data.get('league') not in ('','all'): self.add_error('league','OddsPortal 목록 배당은 리그 전체를 선택해 주세요.')
            if 'mode' not in self.fields: self.add_error('bookmaker','목록 표시 배당은 예정·과거 경기 화면에서 수집해 주세요.')
        data['target_bookmaker']=target
        if data.get('day'):
            selected=datetime.fromisoformat(str(self.data.get('day')))
            selected=selected.replace(tzinfo=ZoneInfo('Asia/Seoul')) if selected.tzinfo is None else selected.astimezone(ZoneInfo('Asia/Seoul'))
            data['starts_from']=selected
            data['day']=selected.date()
        sport=data.get('sport');mode=data.get('mode');league=data.get('league','').strip('/')
        prefix='hockey' if sport=='ice-hockey' else sport
        if league not in ('','all') and sport!='all' and not league.startswith(((sport or '')+'/',(prefix or '')+'/')): self.add_error('league','선택 종목에 해당하는 리그를 선택하세요.')
        if mode=='historic' and not league: self.add_error('league','리그 또는 전체를 선택하세요. 각 리그의 최근 결과 1페이지에서 수집합니다.')
        if mode=='upcoming' and data.get('day') and data['day']<timezone.now().astimezone(ZoneInfo('Asia/Seoul')).date(): self.add_error('day','과거 결과는 과거 경기·결과 수집을 선택하세요.')
        data['league']=league
        data['markets']=data.get('market_set','winner') if sport=='all' or data.get('market_set')=='all' else markets_for(sport,data.get('market_set','winner')) if sport in WINNER else 'winner'
        return data


class InplayForm(CollectionForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields.pop('mode');self.fields.pop('day')
        self.fields['league'].help_text='현재 진행 중인 경기에서 수집할 리그를 선택하세요.'
        self.fields['limit'].label='최대 상세 수집 경기 수 (종목별)'
    def clean(self):
        data=super().clean()
        data.update(mode='live',day=timezone.now().astimezone(ZoneInfo('Asia/Seoul')).date(),starts_from=None)
        return data


def upcoming_selected(row,plan):
    if plan.mode!='upcoming' or not getattr(plan,'starts_from',None): return True
    raw=row.get('kickoff_utc') or row.get('match_date')
    if not raw: return True
    try: value=datetime.strptime(raw,'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=UTC)
    except ValueError: return False
    return value.astimezone(ZoneInfo('Asia/Seoul')).date()==plan.day and value>=plan.starts_from


def python_path():
    return ROOT/'tools/harvester/.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')


def safe_link(value):
    p=urlsplit(value)
    if p.scheme!='https' or p.netloc!='www.oddsportal.com' or p.query or not re.fullmatch(r'/[a-z-]+/h2h/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/?',p.path) or not re.fullmatch(r'[a-zA-Z0-9]+',p.fragment):
        raise ValueError('지원되지 않는 경기 주소입니다.')
    return value


def price(value):
    try:
        n=Decimal(str(value));return float(n) if n.is_finite() and 1<n<=1000000 else None
    except (InvalidOperation,ValueError): return None


def normalize(raw,job):
    target=getattr(job,'target_bookmaker','')
    raw=deepcopy(raw)
    if target:
        for key,value in raw.items():
            if key.endswith('_market') and isinstance(value,list):
                raw[key]=[row for row in value if str(row.get('bookmaker_name','')).strip().casefold()==target.casefold()]
    url=safe_link(raw['match_link'])
    home,away=raw.get('home_team'),raw.get('away_team')
    if not isinstance(home,str) or not home or not isinstance(away,str) or not away: raise ValueError('팀명이 없는 수집 항목입니다.')
    start=''
    if raw.get('match_date'):
        start=datetime.strptime(raw['match_date'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=UTC).isoformat()
    scores=[]
    live=bool(raw.get('live_period'))
    for name,key in ((home,'live_score_home' if live else 'home_score'),(away,'live_score_away' if live else 'away_score')):
        value=raw.get(key)
        if value is not None and str(value).isdigit(): scores.append({'name':name,'score':str(value)})
    # Upcoming pages may contain a score but do not prove a final state.
    completed=job.mode=='historic' and len(scores)==2 and not live
    books={}
    for token,rows in raw.items():
        if not token.endswith('_market') or not isinstance(rows,list): continue
        key=token[:-7]
        for row in rows:
            book_name=row.get('bookmaker_name')
            if not book_name: continue  # Preview best prices are not an identified bookmaker.
            blocked=set(row.get('blocked_outcomes',[]));out=[]
            field_names=[('1',home),('X','Draw'),('2',away),('player_1',home),('player_2',away),('team1_handicap',home),('team2_handicap',away),('handicap_team_1',home),('handicap_team_2',away),('odds_over','Over'),('odds_under','Under')]
            field_names += [('btts_yes','양팀 득점 예'),('btts_no','양팀 득점 아니오'),('1X','홈·무승부'),('12','홈·원정'),('X2','무승부·원정'),('dnb_team1',home),('dnb_team2',away),('games_handicap_player_1',home),('games_handicap_player_2',away),('sets_handicap_player_1',home),('sets_handicap_player_2',away),('correct_score',key)]
            for field,name in field_names:
                value=price(row.get(field))
                if value is not None and field not in blocked: out.append({'name':name,'price':value})
            if not out: continue
            book_key=hashlib.sha256(book_name.encode()).hexdigest()[:16]
            book=books.setdefault(book_key,{'key':book_key,'title':book_name,'markets':[]})
            simple=key in ('1x2','home_away','match_winner')
            line=re.fullmatch(r'(asian_handicap|over_under)_(?:games_)?([+-]?\d+(?:_\d+)?)(?:_games)?',key)
            market_key='h2h' if simple else key
            if line:
                point=float(line[2].replace('_','.'))
                market_key='spreads' if line[1]=='asian_handicap' else 'totals'
                for outcome in out: outcome['point']=-point if market_key=='spreads' and outcome['name']==away else point
            book['markets'].append({'key':market_key,'title':key+' · '+str(row.get('period','')),'period':row.get('period'),'outcomes':out})
    league=raw.get('league_name') or (job.league if ',' not in job.league else '') or '리그 미확인'
    return {'id':'oh-'+urlsplit(url).fragment,'url':url,'home':home,'away':away,'startsAt':start,'sport':job.sport,'group':dict(SPORTS).get(job.sport,job.sport),'league':league,'leagueKey':league, 'status':'finished' if completed else 'live' if live else 'upcoming' if job.mode=='upcoming' and not scores else 'unknown','completed':completed,'scores':scores if len(scores)==2 else [],'bookmakers':list(books.values()),'raw':deepcopy(raw),'targetBookmaker':target,'harvesterVersion':'0.20.0','receivedAt':timezone.now().isoformat()}


@transaction.atomic
def merge(records,job):
    model=InplaySnapshot if job.mode=='live' else HarvesterSnapshot
    state,_=model.objects.get_or_create(pk=1)
    state=model.objects.select_for_update().get(pk=1)
    items={event['id']:event for event in state.payload.get('items',[])}
    for event in records:
        old=items.get(event['id'])
        if old and (old['home'],old['away'])!=(event['home'],event['away']): raise ValueError('경기 ID와 팀 정보가 충돌했습니다.')
        if old and old.get('completed') and not event.get('completed'): continue
        items[event['id']]=event
    state.payload={'source':'OddsHarvester','version':'0.20.0','items':list(items.values())[-20000:],'lastJob':job.pk}
    state.fetched_at=timezone.now();state.save()


def expire_stale():
    Job.objects.filter(active_key='harvester',updated_at__lt=timezone.now()-timedelta(minutes=3)).update(active_key=None,status='failed',error='수집 작업의 응답이 끊겼습니다. 다시 실행해 주세요.',finished_at=timezone.now())


def start_job(user,data):
    expire_stale()
    try:
        with transaction.atomic(): job=Job.objects.create(requested_by=user,starts_from=data.get('starts_from'),target_bookmaker=data.get('target_bookmaker',''),**{k:data[k] for k in ('sport','mode','day','league','markets','limit')})
    except IntegrityError: return Job.objects.get(active_key='harvester'),False
    options={'cwd':str(ROOT),'stdin':subprocess.DEVNULL,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL,'env':{**os.environ,'EVEPREVIEW_JOB_DATABASE':str(settings.DATABASES['default']['NAME'])}}
    if os.name=='nt': options['creationflags']=subprocess.CREATE_NO_WINDOW
    try: subprocess.Popen([sys.executable,str(settings.BASE_DIR/'manage.py'),'collect_harvester',str(job.pk)],**options)
    except OSError:
        Job.objects.filter(pk=job.pk).update(active_key=None,status='failed',error='수집 작업을 시작하지 못했습니다.',finished_at=timezone.now());job.refresh_from_db()
    return job,True


def run_cli(job,args,output,command_override=None):
    if not python_path().exists(): raise ValueError('Harvester 전용 가상환경이 없습니다. tools/harvester/README.md를 확인하세요.')
    command=[str(python_path()),'-m','oddsharvester',*args,'--timezone','Asia/Seoul','--locale','en-US','--headless','--concurrency','1','--request-delay','2','-f','json','-o',str(output)]
    env={k:v for k,v in os.environ.items() if not k.startswith(('ODDSHARVESTER_','OH_'))}
    env['PYTHONIOENCODING']='utf-8'
    if command_override is not None: command=command_override
    with tempfile.TemporaryFile() as log:
        options={'stdout':log,'stderr':log,'env':env,'cwd':str(output.parent)}
        if os.name=='nt': options['creationflags']=subprocess.CREATE_NO_WINDOW
        process=subprocess.Popen(command,**options);started=time.monotonic()
        try:
            while process.poll() is None:
                if not Job.objects.filter(pk=job.pk,active_key='harvester').exists(): raise ValueError('관리자가 수집을 중지했습니다.')
                if time.monotonic()-started>1800: raise ValueError('수집 제한 시간(30분)을 초과했습니다.')
                Job.objects.filter(pk=job.pk).update(updated_at=timezone.now())
                time.sleep(2)
        finally:
            if process.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
                else: process.terminate()
                process.wait(timeout=15)
        log.seek(0);message=log.read().decode('utf-8',errors='replace')
    rows=json.loads(output.read_text(encoding='utf-8')) if output.exists() else []
    if not isinstance(rows,list): raise ValueError('Harvester 응답 형식이 잘못되었습니다.')
    if process.returncode and not rows:
        explanation=next((line for line in message.splitlines() if line.startswith('Error:')),'외부 페이지 응답 또는 수집 로그를 확인해 주세요.')
        raise ValueError('Harvester가 데이터를 반환하지 못했습니다. '+explanation[:450])
    return rows,process.returncode


def representative_event(row,plan):
    url=safe_link(row['url'])
    home,away=row['home'],row['away']
    if not home or not away: raise ValueError('팀명 누락')
    completed=row.get('status')=='finished'
    scores=row.get('scores') or []
    if completed and (len(scores)!=2 or not all(isinstance(n,int) and n>=0 for n in scores)):
        raise ValueError('완료 점수 미확인')
    start=''
    if row.get('status')=='scheduled':
        clock=datetime.strptime(row['statusText'],'%H:%M').time()
        value=datetime.combine(plan.day,clock,tzinfo=ZoneInfo('Asia/Seoul'))
        if plan.starts_from and value<plan.starts_from: return None
        start=value.astimezone(UTC).isoformat()
    if (plan.mode=='upcoming' and row.get('status')!='scheduled') or (plan.mode=='historic' and not completed): return None
    # Preserve column positions, including unavailable prices; no market inference.
    odds=row.get('odds',[])
    outcomes=[{'name':f'표시 {index+1}','price':value,'displayColumn':index}
              for index,raw in enumerate(odds) if (value:=price(raw)) is not None]
    return {'id':'oh-'+urlsplit(url).fragment,'url':url,'home':home,'away':away,
            'startsAt':start,'statusText':row.get('statusText',''),'sport':plan.sport,
            'group':dict(SPORTS).get(plan.sport,plan.sport),'league':row.get('leagueText',''),
            'leagueKey':row.get('leagueText',''),'status':'finished' if completed else 'upcoming',
            'completed':completed,'scores':[{'name':name,'score':str(n)} for name,n in zip((home,away),scores)],
            'bookmakers':[{'key':'oddsportal-listing','title':'OddsPortal 목록 표시 배당 (업체 미식별)',
                           'markets':[{'key':'portal_display','title':'목록 표시 순서 · 시장 미식별','outcomes':outcomes}]}] if outcomes else [],
            'targetBookmaker':'OddsPortal (listing)','raw':deepcopy(row),
            'provenance':{'type':'listing','page':row.get('sourcePage',''),'bookmakerIdentified':False},
            'receivedAt':timezone.now().isoformat()}


def collect_representative(job,plan,folder):
    if plan.mode=='live' or job.league not in ('','all'): raise ValueError('목록 배당은 리그 전체의 예정·과거 경기에서 지원합니다.')
    config=folder/'listing-config.json'
    config.write_text(json.dumps({'sport':'hockey' if plan.sport=='ice-hockey' else plan.sport,'day':plan.day.strftime('%Y%m%d')}),encoding='utf-8')
    node=os.environ.get('NODE_BINARY') or ('C:/Program Files/nodejs/node.exe' if os.name=='nt' else 'node')
    rows,code=run_cli(job,[],folder/'listing.json',command_override=[node,str(ROOT/'tools/oddsportal/representative.cjs'),str(config),str(folder/'listing.json')])
    if code: raise ValueError('목록 수집이 완료되지 않아 저장하지 않았습니다.')
    events=[]
    for row in rows:
        event=representative_event(row,plan)
        if event: events.append(event)
    return events[:plan.limit] if plan.limit else events


def run_job(job_id):
    if not Job.objects.filter(pk=job_id,status='queued',active_key='harvester').update(status='running',updated_at=timezone.now()): return
    job=Job.objects.get(pk=job_id)
    try:
        plans=list(plans_for(job));ids=set();errors=[];completed_plans=0
        for index,plan in enumerate(plans):
            if not Job.objects.filter(pk=job.pk,active_key='harvester').exists(): return
            Job.objects.filter(pk=job.pk).update(progress=f'{index+1}/{len(plans)} · {plan.sport} · {plan.mode} 목록 수집 중')
            try:
                with tempfile.TemporaryDirectory(prefix='eve-harvester-') as directory:
                    folder=Path(directory)
                    if plan.target_bookmaker=='OddsPortal (listing)':
                        normalized=collect_representative(job,plan,folder)
                        with transaction.atomic():
                            locked=Job.objects.select_for_update().get(pk=job.pk)
                            if locked.active_key is None: return
                            merge(normalized,plan);ids.update(event['id'] for event in normalized)
                            Job.objects.filter(pk=job.pk).update(match_count=len(ids),updated_at=timezone.now())
                        completed_plans+=1
                        continue
                    listing=[plan.mode,'-s',plan.sport,'--links-only']
                    if plan.league: listing+=['-l',plan.league]
                    if plan.mode=='historic': listing+=['--season','current','--max-pages','1']
                    elif plan.mode=='upcoming' and not plan.league: listing+=['-d',job.day.strftime('%Y%m%d')]
                    links,listing_code=run_cli(job,listing,folder/'links.json')
                    selected=list(dict.fromkeys(safe_link(row['match_link']) for row in links if upcoming_selected(row,plan)))
                    if job.limit: selected=selected[:job.limit]
                    if not Job.objects.filter(pk=job.pk,active_key='harvester').update(progress=f'{index+1}/{len(plans)} · {plan.sport} · {plan.mode} · {len(selected)}경기 상세 수집 중'): return
                    rows=[];code=0
                    if selected:
                        (folder/'links.txt').write_text('\n'.join(selected),encoding='utf-8')
                        arguments=[plan.mode,'-s',plan.sport,'--match-links-file',str(folder/'links.txt'),'-m',plan.markets]
                        if plan.target_bookmaker: arguments+=['--target-bookmaker',plan.target_bookmaker]
                        rows,code=run_cli(job,arguments,folder/'details.json')
                    normalized=[];invalid=0
                    for row in rows:
                        try:
                            if plan.mode=='upcoming' and plan.starts_from and not row.get('match_date'): invalid+=1;continue
                            if not upcoming_selected(row,plan): continue
                            event=normalize(row,plan)
                            if plan.mode=='historic' and not event['completed']: invalid+=1;continue
                            normalized.append(event)
                        except (ValueError,KeyError,TypeError): invalid+=1
                    missing_odds=sum(not event['bookmakers'] for event in normalized)
                    if missing_odds: errors.append(f'업체별 배당이 없는 경기 {missing_odds}개.'+(f' 지정 업체: {plan.target_bookmaker}.' if plan.target_bookmaker else ''))
                    if invalid: errors.append(f'완료 점수 또는 경기 정보 미확인 {invalid}개 항목 제외.')
                    if listing_code or code or len(rows)<len(selected): errors.append(f'{plan.sport}/{plan.mode}: 일부 수집 실패.')
                    with transaction.atomic():
                        locked=Job.objects.select_for_update().get(pk=job.pk)
                        if locked.active_key is None: return
                        merge(normalized,plan);ids.update(event['id'] for event in normalized)
                        Job.objects.filter(pk=job.pk).update(match_count=len(ids),updated_at=timezone.now())
                        completed_plans+=1
            except Exception as exc:
                errors.append(f'{plan.sport}/{plan.mode}: {str(exc)[-300:]}')
        Job.objects.filter(pk=job.pk,active_key='harvester').update(match_count=len(ids),status='partial' if errors and completed_plans else 'failed' if errors else 'complete',progress=f'{len(plans)}개 수집 범위 처리 · 저장 {len(ids)}경기',error=' '.join(errors)[-1000:],active_key=None,finished_at=timezone.now(),updated_at=timezone.now())
    except Exception as exc:
        Job.objects.filter(pk=job.pk,active_key='harvester').update(status='failed',error=str(exc)[-1000:],active_key=None,finished_at=timezone.now(),updated_at=timezone.now())
