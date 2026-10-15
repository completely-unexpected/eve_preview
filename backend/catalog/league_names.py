"""Display translations only. Provider identifiers and stored data stay unchanged."""
from copy import deepcopy

NAMES = {
    '3. Liga - Germany':'독일 3부 리그', 'A-League':'호주 A리그', "AFL Women's":'호주 여자 풋볼 리그',
    'AHL':'북미 AHL 하키', 'ATP Shanghai Masters':'ATP 상하이 마스터스', 'Allsvenskan - Sweden':'스웨덴 알스벤스칸',
    'Austrian Football Bundesliga':'오스트리아 분데스리가', 'Basketball Euroleague':'농구 유로리그', 'Boxing':'권투',
    'Brazil Série A':'브라질 세리에 A', 'Brazil Série B':'브라질 세리에 B', 'Bundesliga - Germany':'독일 분데스리가',
    'Bundesliga 2 - Germany':'독일 분데스리가 2부', 'CFL':'캐나다 풋볼 리그', 'Championship':'잉글랜드 챔피언십',
    'Copa Libertadores':'코파 리베르타도레스', 'Copa Sudamericana':'코파 수다메리카나', 'DFB-Pokal':'독일 DFB 포칼',
    'Denmark Superliga':'덴마크 수페르리가', 'Dutch Eredivisie':'네덜란드 에레디비시', 'EFL Cup':'잉글랜드 리그컵',
    'EPL':'잉글랜드 프리미어리그', 'Ekstraklasa - Poland':'폴란드 엑스트라클라사', 'Eliteserien - Norway':'노르웨이 엘리테세리엔',
    'Frauen-Bundesliga':'독일 여자 분데스리가', 'Handball-Bundesliga':'독일 핸드볼 분데스리가', 'HockeyAllsvenskan':'스웨덴 하키 알스벤스칸',
    'International Twenty20':'국제 T20 크리켓', 'J League':'일본 J리그', 'K League 1':'한국 K리그 1', 'KBO':'한국 프로야구',
    'La Liga - Spain':'스페인 라리가', 'La Liga 2 - Spain':'스페인 라리가 2부', 'League 1':'잉글랜드 리그 1',
    'League 2':'잉글랜드 리그 2', 'League of Ireland':'아일랜드 리그', 'Liga MX':'멕시코 리가 MX',
    'Ligue 1 - France':'프랑스 리그 1', 'Ligue 2 - France':'프랑스 리그 2', 'Liiga':'핀란드 리가',
    'MLB':'미국 메이저리그', 'MLS':'미국 메이저리그 사커', 'MMA':'종합격투기', 'Mestis':'핀란드 메스티스',
    'NBA':'미국 프로농구', 'NBA Preseason':'미국 프로농구 프리시즌', 'NBL':'호주 프로농구',
    'NCAAF':'미국 대학 풋볼', 'NFL':'미국 프로풋볼', 'NHL':'북미 아이스하키', 'NPB':'일본 프로야구',
    'One Day Internationals':'국제 원데이 크리켓', 'Premiership - Scotland':'스코틀랜드 프리미어십',
    'Primeira Liga - Portugal':'포르투갈 프리메이라리가', 'Primera División - Argentina':'아르헨티나 프리메라 디비시온',
    'Primera División - Chile':'칠레 프리메라 디비시온', 'SHL':'스웨덴 하키 리그', 'Saudi Pro League':'사우디 프로리그',
    'Serie A - Italy':'이탈리아 세리에 A', 'Serie B - Italy':'이탈리아 세리에 B', 'Super League - China':'중국 슈퍼리그',
    'Super League - Greece':'그리스 슈퍼리그', 'Superettan - Sweden':'스웨덴 수페레탄', 'Swiss Superleague':'스위스 슈퍼리그',
    'Test Matches':'테스트 크리켓', 'Turkey Super League':'튀르키예 쉬페르리그',
    'UEFA Champions League':'UEFA 챔피언스리그', 'UEFA Europa Conference League':'UEFA 컨퍼런스리그',
    'UEFA Europa League':'UEFA 유로파리그', 'UEFA Nations League':'UEFA 네이션스리그',
    'Veikkausliiga - Finland':'핀란드 베이카우스리가', 'WNBA':'미국 여자 프로농구', 'WTA Wuhan Open':'WTA 우한 오픈',
    'Ligue 1':'리그 1', 'Ligue 2':'리그 2', 'Liga Profesional':'리가 프로페시오날', 'Reserve League':'리저브 리그',
    'AFC Champions League 2':'AFC 챔피언스리그 2', 'Gulf Club Champions League':'걸프 클럽 챔피언스리그',
    'Australian Championship':'오스트레일리안 챔피언십', 'I Liqa':'1부 리그', 'Vysshaya Liga':'비샤야 리가',
    'Premier League':'프리미어리그', 'Copa do Brasil U20':'브라질 U20 컵', 'Copa do Brasil Women':'브라질 여자 컵',
    'Pernambucano U20':'페르남부쿠 U20 리그', 'Pro Cup':'프로컵', 'Copa Colombia':'코파 콜롬비아',
    'Primera A':'프리메라 A', 'Primera B':'프리메라 B', 'Primera Division':'프리메라 디비시온',
    'Cyprus Cup':'키프로스컵', 'Chance Liga':'찬스 리가', 'Division 2 A':'디비전 2 A', 'Champions League':'챔피언스리그',
}
REGIONS = {'Algeria':'알제리','Argentina':'아르헨티나','Asia':'아시아','Australia':'호주','Azerbaijan':'아제르바이잔',
    'Belarus':'벨라루스','Botswana':'보츠와나','Brazil':'브라질','Bulgaria':'불가리아','Colombia':'콜롬비아',
    'Costa Rica':'코스타리카','Cyprus':'키프로스','Czech Republic':'체코','Egypt':'이집트','Europe':'유럽','USA':'미국',
    'England':'잉글랜드','Spain':'스페인','Germany':'독일','France':'프랑스','Italy':'이탈리아','Japan':'일본','South Korea':'한국'}


def league_name(value):
    value = str(value or '')
    if value in NAMES: return NAMES[value]
    return ' / '.join(REGIONS.get(part.strip(), NAMES.get(part.strip(), part.strip())) for part in value.split('/'))


def localize_events(items):
    result = deepcopy(items)
    for event in result:
        if 'league' in event:
            event['leagueOriginal'] = event.get('leagueOriginal', event['league'])
            event['league'] = league_name(event['league'])
    return result


def localize_leagues(items):
    result = deepcopy(items)
    for item in result:
        item['titleOriginal'] = item.get('titleOriginal', item.get('title', ''))
        item['title'] = league_name(item.get('title', ''))
    return result
