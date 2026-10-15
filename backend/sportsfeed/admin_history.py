from decimal import Decimal, InvalidOperation
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from zoneinfo import ZoneInfo

STATES={'pending':'정산 대기','won':'적중','lost':'낙첨','void':'취소','mixed':'혼합 결과'}
MARKETS={'h2h':'승무패','spreads':'핸디캡','totals':'오버언더','general_parity':'일반볼 홀/짝','general_range':'일반볼 구간','power_parity':'파워볼 홀/짝','power_range':'파워볼 언더/오버'}
OPTIONS=[('general_parity',['홀','짝']),('general_range',['대 (81~130)','중 (65~80)','소 (15~64)']),('power_parity',['홀','짝']),('power_range',['언더 (0~4)','오버 (5~9)'])]


def price(value):
    try:
        number=Decimal(str(value))
        return f'{number:.2f}' if number.is_finite() else ''
    except (InvalidOperation,ValueError,TypeError): return ''


def local_time(value):
    try:
        parsed=parse_datetime(value or '')
        return parsed.astimezone(ZoneInfo('Asia/Seoul')).strftime('%m-%d %H:%M') if parsed and parsed.tzinfo else ''
    except (ValueError,TypeError): return ''


def ticket(slip,can_settle):
    rows=[];groups={};odds=Decimal(1);prices=[]
    for leg in slip.results.all():
        pick=leg.selection
        shown=price(pick.get('price'));prices.append(shown)
        try: odds*=Decimal(str(pick['price']))
        except (InvalidOperation,ValueError,TypeError,KeyError): odds=Decimal(0)
        row={'pick':pick,'time':local_time(pick.get('startsAt')),'result':leg.result,'result_label':STATES.get(leg.result,'대기'),'price':shown,'home_selected':pick.get('name')==pick.get('home'),'away_selected':pick.get('name')==pick.get('away'),'draw_selected':pick.get('name')=='Draw','market_label':MARKETS.get(pick.get('market'),pick.get('market',''))}
        name=pick.get('name','')
        row['middle']=shown if row['draw_selected'] else str(pick['point']) if pick.get('point') is not None else 'VS'
        if not any((row['home_selected'],row['away_selected'],row['draw_selected'])):
            row['other_selected']=True
            row['middle']=f"{ {'Over':'오버','Under':'언더'}.get(name,name)} {pick.get('point') if pick.get('point') is not None else ''} · {shown}"
        rows.append(row)
        key=pick.get('eventId') or str(pick.get('startsAt'))+'|'+str(pick.get('away'))
        groups.setdefault(key,[]).append(row)
    power=[]
    for group in groups.values():
        columns=[]
        for market,names in OPTIONS:
            selected=[row['pick'].get('name') for row in group if row['pick'].get('market')==market]
            columns.append([{'name':name,'selected':name in selected} for name in dict.fromkeys([*names,*selected])])
        power.append({'pick':group[0]['pick'],'time':group[0]['time'],'columns':columns,'legs':group,'prices':' / '.join(row['price'] for row in group)})
    return {'slip':slip,'rows':rows,'power':power,'status_label':STATES.get(slip.status,slip.status),'odds':price(odds) if slip.mode=='multi' else ' / '.join(prices),'amount':f'{slip.total_stake:,}원','expected':f'{slip.expected_return:,}원','credited':f'{slip.credited_amount:,}원','can_settle':can_settle and slip.status=='pending','url':reverse('admin:sportsfeed_demoslip_change',args=[slip.pk]),'action_url':reverse('admin:sportsfeed_demoslip_settle',args=[slip.pk])}
