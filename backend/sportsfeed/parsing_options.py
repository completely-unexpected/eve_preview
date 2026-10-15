from django import forms
from .harvester import SPORTS
from .models import OddsPortalSnapshot
from catalog.odds import categorize


class ParsingForm(forms.Form):
    sport=forms.ChoiceField(label='종목',choices=[('all','전체'),*SPORTS])
    league=forms.ChoiceField(label='리그',choices=[('all','전체')])
    status=forms.ChoiceField(label='경기 상태',choices=[('all','전체'),('upcoming','예정'),('finished','종료'),('cancelled','취소·연기')])
    odds=forms.ChoiceField(label='배당 유무',choices=[('all','전체'),('with','배당 있음'),('without','배당 없음')])
    limit=forms.TypedChoiceField(label='최대 저장 경기 수',coerce=int,choices=[(0,'전체'),(20,'20'),(50,'50'),(100,'100'),(500,'500')])
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        state=OddsPortalSnapshot.objects.filter(pk=1).first()
        leagues={item['leagueKey']:item['league'] for item in categorize(state.payload.get('items',[]),'oddsportal')} if state else {}
        self.fields['league'].choices=[('all','전체'),*sorted(leagues.items(),key=lambda row:row[1])]


def filter_items(items,options,remaining=None):
    if not options: return items
    allowed=[]
    categorized=categorize(items,'oddsportal')
    for raw,item in zip(items,categorized):
        if item.get('status')=='live': continue
        sport='ice-hockey' if item.get('sportKey')=='hockey' else item.get('sportKey')
        if options.get('sport','all')!='all' and sport!=options['sport']: continue
        if options.get('league','all')!='all' and item.get('leagueKey')!=options['league']: continue
        if options.get('status','all')!='all' and item.get('status')!=options['status']: continue
        if options.get('odds')=='with' and not item.get('odds'): continue
        if options.get('odds')=='without' and item.get('odds'): continue
        allowed.append(raw)
    return allowed if remaining is None else allowed[:max(remaining,0)]
