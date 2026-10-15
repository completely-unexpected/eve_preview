"""Bridge verified public final scores onto existing provider event identities."""
from copy import deepcopy
from datetime import timedelta
import re
import unicodedata
from zoneinfo import ZoneInfo
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import FeedSnapshot

SPORTS={'Soccer':'football','Baseball':'baseball','Basketball':'basketball','Ice Hockey':'hockey','Tennis':'tennis','American Football':'american-football','Cricket':'cricket'}
LEAGUES={
    'baseball_kbo':('kbo',),'baseball_npb':('npb',),'baseball_mlb':('mlb',),
    'basketball_nbl':('nbl',),'basketball_nba_preseason':('nba-pre-season','nba-preseason','nba'),
    'basketball_euroleague':('euroleague',),
    'icehockey_nhl':('nhl',),'icehockey_ahl':('ahl',),'icehockey_liiga':('liiga',),
    'icehockey_sweden_allsvenskan':('hockeyallsvenskan','allsvenskan'),
    'soccer_usa_mls':('mls',),'soccer_conmebol_copa_libertadores':('copa-libertadores',),
    'soccer_conmebol_copa_sudamericana':('copa-sudamericana',),
    'soccer_argentina_primera_division':('liga-profesional','primera-division'),
    'americanfootball_ncaaf':('ncaa','ncaa-football'),
    'tennis_atp_shanghai_masters':('shanghai','atp-shanghai'),'tennis_wta_wuhan_open':('wuhan','wta-wuhan'),
    'cricket_odi':('one-day-international','odi'),'cricket_international_t20':('twenty20-international','t20-international'),
}


def name_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum() and not unicodedata.combining(c))


ALIASES={
    'baseball_npb':{'Yokohama DeNA BayStars':'Yokohama BayStars','Fukuoka SoftBank Hawks':'Fukuoka S. Hawks','Hokkaido Nippon-Ham Fighters':'Nippon Ham Fighters'},
    'basketball_nbl':{'Sydney Kings':'Sydney'},
    'basketball_euroleague':{'Beşiktaş J.K.':'Besiktas','FC Bayern München':'Bayern','Paris Basketball':'Paris','Virtus Segafredo Bologna':'Virtus Bologna'},
    'soccer_usa_mls':{'Seattle Sounders FC':'Seattle Sounders','St. Louis City SC':'St. Louis City','Vancouver Whitecaps FC':'Vancouver Whitecaps','Minnesota United FC':'Minnesota United','Atlanta United FC':'Atlanta Utd','Columbus Crew SC':'Columbus Crew','Charlotte FC':'Charlotte','Inter Miami CF':'Inter Miami','New York City FC':'New York City','Orlando City SC':'Orlando City','LA Galaxy':'Los Angeles Galaxy'},
    'soccer_argentina_primera_division':{'Sarmiento de Junin':'Sarmiento Junin'},
    'americanfootball_ncaaf':{'Sam Houston State Bearkats':'Sam Houston State','Western Kentucky Hilltoppers':'Western Kentucky','Missouri State Bears':'Missouri State','Kennesaw State Owls':'Kennesaw State'},
    'tennis_atp_shanghai_masters':{'Daniil Medvedev':'Medvedev D.','Stefanos Tsitsipas':'Tsitsipas S.','Tommy Paul':'Paul T.','Zizou Bergs':'Bergs Z.'},
}


def team_key(value,league):
    aliases={name_key(key):name_key(alias) for key,alias in ALIASES.get(league,{}).items()}
    return aliases.get(name_key(value),name_key(value))


def eligible(event,now):
    start=parse_datetime(event.get('startsAt',''))
    return bool(start and timezone.is_aware(start) and start<=now and not event.get('completed') and event.get('status') not in ('finished','cancelled'))


def candidate(event,result):
    parts=result.get('leaguePath','').strip('/').split('/')
    if len(parts)!=3 or parts[0]!=SPORTS.get(event.get('group')): return False
    if parts[2] not in LEAGUES.get(event.get('leagueKey'),()): return False
    league=event.get('leagueKey')
    if team_key(event['home'],league)!=team_key(result.get('home',''),league) or team_key(event['away'],league)!=team_key(result.get('away',''),league): return False
    day=parse_datetime(event['startsAt']).astimezone(ZoneInfo('Asia/Seoul')).date().isoformat()
    return day==result.get('sourceDay')


@transaction.atomic
def apply_results(results):
    state=FeedSnapshot.objects.select_for_update().filter(pk=1).first()
    if not state: return {'updated':0,'unresolved':0}
    payload=deepcopy(state.payload);items=payload.get('items',[]);now=timezone.now()
    pending=[event for event in items if eligible(event,now)]
    finals=[result for result in results if (result.get('status')=='finished' or result.get('statusText','').casefold() in ('after ot','after et','after penalties','aet')) and isinstance(result.get('scores'),list) and len(result['scores'])==2 and all(type(value) is int and value>=0 for value in result['scores'])]
    # A pair playing twice on the same day cannot be matched without start times.
    matches={event['id']:[result for result in finals if candidate(event,result)] for event in pending}
    usage={}
    for candidates in matches.values():
        for result in candidates: usage[result['id']]=usage.get(result['id'],0)+1
    updated=[]
    for event in pending:
        options={result['id']:result for result in matches[event['id']]}
        if len(options)!=1: continue
        result=next(iter(options.values()))
        if usage[result['id']]!=1: continue
        event.update(completed=True,status='completed',scores=[{'name':event['home'],'score':str(result['scores'][0])},{'name':event['away'],'score':str(result['scores'][1])}],
            resultSource={'provider':'OddsPortal','eventId':result['id'],'url':result['url'],'leaguePath':result['leaguePath'],'sourceDay':result['sourceDay'],'receivedAt':now.isoformat()})
        updated.append(event['id'])
    report={'at':now.isoformat(),'updated':len(updated),'eventIds':updated,'unresolved':len(pending)-len(updated),'source':'OddsPortal'}
    payload['lastResultBridge']=report
    state.payload=payload;state.save(update_fields=['payload'])
    return report
