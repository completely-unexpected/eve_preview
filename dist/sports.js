const sportsSlip = {picks: new Map(), mode: 'multi', stake: '', owner: null, pending: null, submitting: false};
let sportsBoardRequest = 0;
let activeSportsFundsRefresh = null;

async function renderSports(mode) {
  const requestId = ++sportsBoardRequest;
  activeSportsFundsRefresh = null;
  const view = document.querySelector('.route-view');
  view.innerHTML = pageHeading(mode === 'inplay' ? '인플레이' : mode === 'esports' ? 'E-스포츠' : '스포츠', '') + '<div id="sports-board" aria-live="polite">전체 경기·배당을 불러오는 중…</div>';
  const panel = view.querySelector('#sports-board');
  const valid = () => requestId === sportsBoardRequest && panel.isConnected;
  const make = (tag, text = '', cls = '') => {const element = document.createElement(tag); element.textContent = text; if (cls) element.className = cls; return element;};
  const format = value => new Intl.NumberFormat('ko-KR').format(value);
  const priceText = value => Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const time = value => Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false}).format(new Date(value)) : '시간 미제공';
  const groupsInfo = {Soccer: ['⚽', '축구'], Basketball: ['🏀', '농구'], Baseball: ['⚾', '야구'], 'Ice Hockey': ['🏒', '아이스하키'], Tennis: ['🎾', '테니스'], Handball: ['🤾', '핸드볼'], Boxing: ['🥊', '권투'], 'Mixed Martial Arts': ['🥋', 'MMA'], MMA: ['🥋', 'MMA'], 'Rugby League': ['🏉', '럭비'], 'American Football': ['🏈', '미식축구'], 'Aussie Rules': ['🏉', '호주식 축구'], Cricket: ['🏏', '크리켓']};
  const marketNames = {h2h: '승무패', spreads: '핸디캡', totals: '오버언더', alternate_spreads: '추가 핸디캡', alternate_totals: '추가 오버언더', btts: '양팀 득점', draw_no_bet: '무승부 제외', team_totals: '팀 오버언더'};
  Object.assign(marketNames, {
    h2h_3_way: '승무패 3방향', alternate_spreads_corners: '추가 코너 핸디캡', alternate_team_totals_corners: '팀 코너 오버언더', alternate_totals_corners: '추가 코너 오버언더',
    correct_score: '정확한 점수', double_chance: '더블찬스', odd_even: '홀짝',
    player_first_goal_scorer: '첫 득점 선수', player_last_goal_scorer: '마지막 득점 선수', player_goal_scorer_anytime: '선수 득점 여부', player_shots: '선수 슈팅', player_shots_on_target: '선수 유효 슈팅', player_goalie_saves_alternate: '골키퍼 세이브',
    player_points: '선수 득점', player_rebounds: '선수 리바운드', player_assists: '선수 어시스트', player_threes: '선수 3점슛', player_pass_yds: '선수 패스 야드', player_rush_yds: '선수 러싱 야드', player_reception_yds: '선수 리시빙 야드'
  });
  function marketName(key) {
    let base = key, suffix = '';
    const period = base.match(/_(h[12]|q[1-4]|p[1-3])$/);
    if (period) {suffix = ' · ' + (period[1] === 'h1' ? '전반전' : period[1] === 'h2' ? '후반전' : period[1][1] + (period[1][0] === 'q' ? '쿼터' : '피리어드')); base = base.slice(0, -period[0].length);}
    const lay = base.endsWith('_lay'); if (lay) base = base.slice(0, -4);
    return (marketNames[base] || base.split('_').map(word => word[0]?.toUpperCase() + word.slice(1)).join(' ')) + (lay ? ' (레이)' : '') + suffix;
  }
  const selectionKey = (event, book, market, outcome) => JSON.stringify([event.id, book.key, market.key, outcome.name, outcome.point, outcome.description]);
  function outcomeLabel(outcome, short = false, event = null) {
    let label = outcome.name === 'Yes' ? '예' : outcome.name === 'No' ? '아니오' : outcome.name === 'Odd' ? '홀' : outcome.name === 'Even' ? '짝' : outcome.name === 'Draw' ? '무승부' : outcome.name === 'Over' ? '오버' : outcome.name === 'Under' ? '언더' : outcome.name;
    if (short && event) label = outcome.name === event.home ? '홈' : outcome.name === event.away ? '원정' : label;
    if (outcome.description) label = outcome.description + ' · ' + label;
    if (outcome.point !== null) label += ' ' + (outcome.name !== 'Over' && outcome.name !== 'Under' && Number(outcome.point) > 0 ? '+' : '') + String(Number(outcome.point));
    return label;
  }
  let wallet = null;
  let limits = null;
  let cash = 0n;
  let quoteRefresh = () => {};
  try {
    const response = await fetch('/api/sports/board/', {cache: 'no-store', credentials: 'same-origin'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || '경기·배당을 불러오지 못했습니다.');
    if (!valid()) return;
    panel.replaceChildren();
    const meta = make('div', '', 'sb-meta');
    meta.append(make('span', data.items.length + '개 경기 · ' + data.completedLeagues.length + '개 리그'));
    panel.append(meta);
    const currentEvents = new Map(data.items.map(event => [event.id, event]));
    for (const [key, pick] of sportsSlip.picks) {
      const event = currentEvents.get(pick.event.id);
      const outcome = event?.bookmakers.find(book => book.key === pick.bookKey)?.markets.find(market => market.key === pick.market)?.outcomes.find(outcome => outcome.name === pick.outcome.name && outcome.point === pick.outcome.point && outcome.description === pick.outcome.description);
      if (!event || !outcome || event.completed || Date.parse(event.startsAt) <= Date.now()) sportsSlip.picks.delete(key);
      else {pick.event = event; pick.outcome = outcome;}
    }
    if (!data.complete) panel.append(make('p', '일부 리그의 조회가 완료되지 않았습니다. 현재 저장된 경기만 표시합니다.', 'wallet-feedback'));
    const eligibleEvents = data.items.filter(event => !event.completed && (mode === 'esports' ? /esport/i.test(event.group + event.leagueKey) : !/esport/i.test(event.group + event.leagueKey)));
    const phaseEvents = eligibleEvents.filter(event => mode === 'inplay' ? event.status === 'live' : event.status !== 'live' && Date.parse(event.startsAt) > Date.now());
    const groups = [...new Set(data.leagues.filter(league => mode === 'esports' ? /esport/i.test(league.group + league.key) : !/esport/i.test(league.group + league.key)).map(league => league.group))];
    const sportOrder = ['Soccer', 'Baseball', 'Basketball'];
    groups.sort((a, b) => {const rank = value => sportOrder.includes(value) ? sportOrder.indexOf(value) : sportOrder.length; return rank(a) - rank(b);});
    let selectedGroup = groups.includes('Soccer') ? 'Soccer' : groups[0] || 'all';
    let selectedEvent = null;
    let selectedBook = '';
    let marketFilter = 'all';
    let page = 1;
    const layout = make('div', '', 'sb-layout');
    const center = make('section', '', 'sb-center');
    const detail = make('section', '', 'sb-detail'); detail.id = 'match-detail';
    const cart = make('aside', '', 'sb-slip'); cart.id = 'betting-cart'; cart.setAttribute('aria-label', '베팅 카트');
    layout.append(center, detail, cart); panel.append(layout);
    const historyBox = make('section', '', 'sb-demo-history'); panel.append(historyBox);
    let historyVersion = 0;
    const phases = make('div', '', 'sb-phase-picker');
    const phaseSelect = document.createElement('select');phaseSelect.setAttribute('aria-label','경기 유형 선택');
    for (const [route, label] of [['sports', '프리매치'], ['inplay', '인플레이'], ...(mode==='esports'?[['esports','E스포츠']]:[])]) {const option=make('option',label);option.value=route;phaseSelect.append(option);}
    phaseSelect.value=mode;phaseSelect.onchange=()=>{location.hash='#/'+phaseSelect.value;};
    phases.append(phaseSelect);layout.before(phases);
    const groupList = make('div', '', 'sb-group-list sb-top-groups');groupList.setAttribute('aria-label','종목 선택');phases.after(groupList);
    const tools = make('div', '', 'sb-tools');
    const search = document.createElement('input'); search.type = 'search'; search.placeholder = '팀 또는 리그 이름을 입력하세요'; search.id = 'match-search'; search.setAttribute('aria-label', '팀 또는 리그 검색');
    const league = document.createElement('select'); league.id = 'match-league'; league.setAttribute('aria-label', '리그 선택');
    const sort = document.createElement('select'); sort.setAttribute('aria-label', '경기 정렬');
    for (const [value, label] of [['time', '시간별 정렬'], ['league', '리그별 정렬']]) {const option = make('option', label); option.value = value; sort.append(option);}
    const refresh = make('button', '↻', 'sb-refresh'); refresh.type = 'button'; refresh.setAttribute('aria-label', '저장된 경기 목록 새로고침'); refresh.onclick = () => renderSports(mode);
    tools.append(search, league, sort, refresh); center.append(tools);
    const count = make('p', '', 'sb-count'); count.id = 'match-count'; center.append(count);
    const list = make('div', '', 'sb-match-list'); list.id = 'match-list'; center.append(list);
    const pagination = make('div', '', 'sb-pagination'); center.append(pagination);
    const cartNotice = make('p', '', 'sb-slip-notice');

    function choose(event, book, market, outcome) {
      if (Date.parse(event.startsAt) <= Date.now() || event.completed) {cartNotice.textContent = '마감된 경기입니다. 목록을 새로고침해 주세요.'; return;}
      const key = selectionKey(event, book, market, outcome);
      if (sportsSlip.picks.has(key)) sportsSlip.picks.delete(key);
      else {
        const already = [...sportsSlip.picks.values()].some(pick => pick.event.id === event.id);
        if (!already && sportsSlip.picks.size >= 20) {cartNotice.textContent = '카트에는 최대 20개 경기를 담을 수 있습니다.'; return;}
        for (const [old, pick] of sportsSlip.picks) if (pick.event.id === event.id) sportsSlip.picks.delete(old);
        sportsSlip.picks.set(key, {event, book: book.title, bookKey: book.key, market: market.key, outcome, key});
      }
      renderCart(); updateSelections();
    }
    function rateButton(event, book, market, outcome, short = false) {
      const button = make('button', '', 'sb-rate'); button.type = 'button'; button.dataset.pick = selectionKey(event, book, market, outcome);
      if(outcome.name !== 'Draw') button.append(make('span', outcomeLabel(outcome, short, event)));
      else {button.classList.add('sb-draw-rate');button.setAttribute('aria-label','무승부 배당 '+priceText(outcome.price));}
      button.append(make('strong', priceText(outcome.price)));
      if(outcome.name === event.away) button.classList.add('sb-away-rate');
      if (Date.parse(event.startsAt) <= Date.now() || event.completed) {button.disabled = true; button.title = '마감된 경기입니다.';}
      if (market.key.endsWith('_lay')) {button.disabled = true; button.title = '레이 시장은 카트 선택을 지원하지 않습니다.';}
      button.setAttribute('aria-pressed', String(sportsSlip.picks.has(button.dataset.pick)));
      button.onclick = () => {selectedEvent = event; selectedBook = book.key; renderDetail(); choose(event, book, market, outcome);};
      return button;
    }
    function updateSelections() {
      for (const button of panel.querySelectorAll('[data-pick]')) button.setAttribute('aria-pressed', String(sportsSlip.picks.has(button.dataset.pick)));
    }
    function setGroup(value) {selectedGroup = value; page = 1; buildGroups(); buildLeagues(); renderList();}
    function buildGroups() {
      groupList.replaceChildren();
      for (const group of ['all', ...groups]) {
        const [icon, name] = group === 'all' ? ['▣', '전체'] : groupsInfo[group] || ['●', group];
        const number = phaseEvents.filter(event => group === 'all' || event.group === group).length;
        const button = make('button', '', 'sb-group ' + (selectedGroup === group ? 'active' : '')); button.type = 'button'; button.dataset.group = group;
        button.append(make('span', icon + ' ' + name), make('strong', String(number))); button.onclick = () => setGroup(group); groupList.append(button);
      }
    }
    function buildLeagues() {
      league.replaceChildren(); const option = make('option', '전체 리그'); option.value = 'all'; league.append(option);
      for (const entry of data.leagues.filter(item => selectedGroup === 'all' || item.group === selectedGroup)) {const option = make('option', entry.title); option.value = entry.key; league.append(option);}
      league.value = 'all';
    }
    function renderList() {
      const query = search.value.trim().toLowerCase();
      const events = phaseEvents.filter(event => (selectedGroup === 'all' || event.group === selectedGroup) && (league.value === 'all' || event.leagueKey === league.value) && (event.home + ' ' + event.away + ' ' + event.league).toLowerCase().includes(query));
      events.sort((a, b) => (sort.value === 'league' ? a.league.localeCompare(b.league) : 0) || a.startsAt.localeCompare(b.startsAt));
      const pages = Math.max(1, Math.ceil(events.length / 40)); page = Math.min(page, pages);
      count.textContent = events.length + '개 경기 · ' + page + '/' + pages + ' 페이지'; list.replaceChildren();
      let lastLeague = '';
      const leagueGroups = new Map();
      for (const event of events.slice((page - 1) * 40, page * 40)) {
        if (!leagueGroups.has(event.leagueKey)) leagueGroups.set(event.leagueKey, []);
        leagueGroups.get(event.leagueKey).push(event);
      }
      for (const event of [...leagueGroups.values()].flat()) {
        if (lastLeague !== event.leagueKey) {list.append(make('h3', event.league, 'sb-league-heading')); lastLeague = event.leagueKey;}
        const row = make('div', '', 'sb-match-row sb-compact-row'); row.dataset.match = event.id;
        const title = make('button', '', 'sb-match-title'); title.type = 'button';
        title.append(make('small', time(event.startsAt)));
        title.onclick = () => {selectedEvent = event; selectedBook = ''; marketFilter = 'all'; renderDetail();}; row.append(title);
        const book = event.bookmakers[0];
        const market = book?.markets.find(item => item.key === 'h2h') || book?.markets.find(item => item.key === 'spreads');
        const prices = make('div', '', 'sb-main-rates');
        const homeName = make('span', event.home, 'sb-row-name');
        const awayName = make('span', event.away, 'sb-row-name sb-away-name');
        if (market) {
          const teamButton = name => {
            const outcome = market.outcomes.find(item => item.name === name);
            if (!outcome) return make('span', '—', 'sb-row-price');
            const button = rateButton(event, book, market, outcome); button.classList.add('sb-row-price');
            button.querySelector('span')?.remove();button.setAttribute('aria-label',name+' 배당 '+priceText(outcome.price));return button;
          };
          prices.append(homeName, teamButton(event.home));
          const draw = market.outcomes.find(item => item.name === 'Draw');
          if (draw) {const button = rateButton(event, book, market, draw);button.classList.add('sb-row-middle');prices.append(button);}
          else {const point = market.outcomes.find(item => item.name === event.home)?.point; prices.append(make('span', point ?? 'VS', 'sb-row-middle'));}
          prices.append(teamButton(event.away), awayName);
        } else {prices.append(homeName, make('span','—','sb-row-price'), make('span', 'VS', 'sb-row-middle'), make('span','—','sb-row-price'), awayName);}
        row.append(prices); list.append(row);
        row.append(make('span', event.scores?.map(item => item.score).join(' : ') || '', 'sb-row-score'));
      }
      pagination.replaceChildren();
      for (const [number, label] of [[page - 1, '‹ 이전'], [page + 1, '다음 ›']]) {const button = make('button', label); button.type = 'button'; button.disabled = number < 1 || number > pages; button.onclick = () => {page = number; renderList(); list.scrollTop = 0;}; pagination.append(button);}
      if (!events.length) list.append(make('p', '표시할 경기가 없습니다.', 'empty-state'));
      if (!selectedEvent || !events.some(event => event.id === selectedEvent.id)) {selectedEvent = events[0] || null; selectedBook = ''; renderDetail();}
      updateSelections();
    }
    function renderDetail() {
      detail.replaceChildren();
      const event = selectedEvent;
      if (!event) {detail.append(make('p', '경기를 선택해 주세요.', 'empty-state')); return;}
      detail.append(make('h2', event.league, 'sb-panel-heading'));
      const scoreboard = make('div', '', 'sb-scoreboard');
      scoreboard.append(make('strong', event.home + ' vs ' + event.away), make('span', time(event.startsAt) + ' (한국 시간)'));
      if (event.scores) scoreboard.append(make('b', event.scores.map(row => row.name + ' ' + row.score).join(' : '), 'sb-score'));
      else scoreboard.append(make('span', '점수 미제공', 'muted'));
      detail.append(scoreboard);
      if (!event.bookmakers.length) {detail.append(make('p', '이 경기의 배당이 아직 제공되지 않았습니다.', 'empty-state')); return;}
      const books = document.createElement('select'); books.className = 'sb-books'; books.setAttribute('aria-label', '배당 제공처');
      for (const book of event.bookmakers) {const option = make('option', book.title + ' · ' + book.markets.length + '개 시장'); option.value = book.key; books.append(option);}
      selectedBook = event.bookmakers.some(book => book.key === selectedBook) ? selectedBook : event.bookmakers[0].key;
      books.value = selectedBook; books.onchange = () => {selectedBook = books.value; renderDetail();}; detail.append(books);
      const book = event.bookmakers.find(item => item.key === selectedBook);
      const tabs = make('div', '', 'sb-market-tabs');
      for (const key of ['all', ...new Set(book.markets.map(item => item.key))]) {const button = make('button', key === 'all' ? '전체' : marketName(key), key === marketFilter ? 'active' : ''); button.type = 'button'; button.onclick = () => {marketFilter = key; renderDetail();}; tabs.append(button);}
      detail.append(tabs);
      const marketList = make('div', '', 'sb-market-list');
      for (const market of book.markets.filter(item => marketFilter === 'all' || item.key === marketFilter)) {
        marketList.append(make('h3', marketName(market.key), 'sb-market-heading'));
        const outcomes = make('div', '', 'sb-outcomes' + (market.outcomes.length === 3 && market.key.startsWith('h2h') ? ' sb-outcomes-three' : ''));
        const ordered = market.key.startsWith('h2h') ? [...market.outcomes].sort((a,b)=>{
          const rank = name => name===event.home?0:name==='Draw'?1:name===event.away?2:3;
          return rank(a.name)-rank(b.name);
        }) : market.outcomes;
        for (const outcome of ordered) outcomes.append(rateButton(event, book, market, outcome));
        marketList.append(outcomes);
        if (market.updatedAt) marketList.append(make('p', '배당 갱신 ' + time(market.updatedAt), 'sb-market-time'));
      }
      if (data.canLoadExtra) {
        const extra = make('button', '이 경기의 세부 시장 불러오기 · 크레딧 사용', 'sb-extra-market-button');
        extra.type = 'button';
        extra.onclick = async () => {
          extra.disabled = true;
          try {
            const session = await getSession();
            const response = await fetch('/api/sports/extra-markets/', {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': session.csrfToken}, body: new URLSearchParams({event_id: event.id})});
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || '세부 배당을 조회하지 못했습니다.');
            if (!valid()) return;
            event.bookmakers = result.event.bookmakers; event.extraMarkets = result.event.extraMarkets;
            for (const [key, pick] of sportsSlip.picks) {
              if (pick.event.id !== event.id) continue;
              const refreshed = event.bookmakers.find(book => book.key === pick.bookKey)?.markets.find(market => market.key === pick.market)?.outcomes.find(outcome => outcome.name === pick.outcome.name && outcome.point === pick.outcome.point && outcome.description === pick.outcome.description);
              if (refreshed) pick.outcome = refreshed; else sportsSlip.picks.delete(key);
            }
            selectedBook = [...event.bookmakers].sort((a, b) => b.markets.length - a.markets.length)[0]?.key || '';
            marketFilter = 'all'; renderList(); renderDetail(); renderCart(); updateSelections();
            cartNotice.textContent = '세부 시장 조회 완료 · 남은 크레딧 ' + result.remainingCredits + (event.extraMarkets.complete ? '' : ' · 크레딧 범위 내 일부 시장만 조회했습니다.');
          } catch (error) {cartNotice.textContent = error.message;}
          finally {extra.disabled = false;}
        };
        detail.append(extra);
      }
      if (event.extraMarkets) detail.append(make('p', '세부 시장 조회 ' + time(event.extraMarkets.fetchedAt), 'sb-market-time'));
      detail.append(marketList); updateSelections();
    }
    function renderCart() {
      historyVersion++;
      cart.replaceChildren(make('h2', '베팅 카트', 'sb-panel-heading'));
      const tabs = make('div', '', 'sb-slip-tabs');
      for (const [value, label] of [['single', '싱글'], ['multi', '멀티']]) {const button = make('button', label, value === sportsSlip.mode ? 'active' : ''); button.type = 'button'; button.onclick = () => {sportsSlip.mode = value; renderCart();}; tabs.append(button);}
      cart.append(tabs);
      const picks = make('div', '', 'sb-picks');
      if (!sportsSlip.picks.size) picks.append(make('p', '⊖\n베팅 카트가 비어 있습니다.', 'sb-empty-slip'));
      for (const [key, pick] of sportsSlip.picks) {
        const row = make('div', '', 'sb-pick'); row.dataset.cartPick = key;
        const remove = make('button', '×', 'sb-remove-pick'); remove.type = 'button'; remove.setAttribute('aria-label', pick.event.home + ' 선택 삭제'); remove.onclick = () => {sportsSlip.picks.delete(key); renderCart(); updateSelections();};
        row.append(remove, make('strong', pick.event.home + ' vs ' + pick.event.away), make('span', marketName(pick.market) + ' · ' + outcomeLabel(pick.outcome)), make('b', priceText(pick.outcome.price)), make('small', pick.book)); picks.append(row);
      }
      cart.append(picks, cartNotice); cartNotice.textContent = '';
      const clear = make('button', '▣ 모두 비우기', 'sb-clear-slip'); clear.type = 'button'; clear.onclick = () => {sportsSlip.picks.clear(); renderCart(); updateSelections();}; cart.append(clear);
      const funds = make('p', wallet ? '사용 가능 금액 ' + format(cash) + '원' : '로그인 후 보유금액을 확인할 수 있습니다.', 'sb-slip-funds'); cart.append(funds);
      const controls = createStakeControls({id: 'cart-stake', value: sportsSlip.stake,
        onChange: (value, error) => {sportsSlip.stake = value; cartNotice.textContent = error; quoteRefresh();},
        onMax: () => {
          if (!wallet) {cartNotice.textContent = '로그인 후 MAX 금액을 사용할 수 있습니다.'; return null;}
          const divisor = sportsSlip.mode === 'single' ? BigInt(Math.max(1, sportsSlip.picks.size)) : 1n;
          const limit = limits ? BigInt(limits[sportsSlip.mode === 'single' ? 'single_max' : 'multi_max']) : 1000000000000n;
          return cash / divisor < limit ? cash / divisor : limit;
        }});
      const {input, stakeValue} = controls; cart.append(controls.root);
      const quote = make('dl', '', 'sb-quote');
      const multiplier = make('dd'); multiplier.id = 'cart-odds'; const outlay = make('dd'); outlay.id = 'cart-total-stake'; const payout = make('dd'); payout.id = 'cart-payout';
      for (const [label, value] of [['전체 배당', multiplier], ['총 베팅금액', outlay], ['예상 당첨금액', payout]]) {const row = make('div'); row.append(make('dt', label), value); quote.append(row);}
      cart.append(quote, make('p', '싱글 금액은 각 경기에 적용됩니다. 한 경기에서는 한 항목만 선택할 수 있습니다.', 'sb-slip-help'));
      const limitsNote = make('p', '', 'sb-slip-limit'); cart.append(limitsNote);
      cart.append(make('p', '현금 가치·환전이 없는 가상머니 테스트입니다. 접수 시 가상머니가 차감됩니다.', 'sb-slip-help'));
      const submit = make('button', sportsSlip.submitting ? '접수 중…' : '배팅하기', 'primary-button sb-submit-bet'); submit.type = 'button'; const availabilityNote = make('p', '', 'sb-slip-help'); cart.append(availabilityNote, submit);
      submit.onclick = async () => {
        if (sportsSlip.submitting) return;
        const body = {mode: sportsSlip.mode, stake: stakeValue().toString(), picks: [...sportsSlip.picks.values()].map(p => ({eventId: p.event.id, bookKey: p.bookKey, market: p.market, name: p.outcome.name, price: p.outcome.price, point: p.outcome.point ?? null, description: p.outcome.description || ''}))};
        const signature = JSON.stringify(body);
        if (!sportsSlip.pending || sportsSlip.pending.signature !== signature) sportsSlip.pending = {signature, requestId: crypto.randomUUID()};
        const attempt = sportsSlip.pending;
        sportsSlip.submitting = true; submit.textContent = '접수 중…'; submit.setAttribute('aria-busy', 'true'); panel.inert = true; submit.disabled = true; cartNotice.textContent = '가상머니 테스트 접수 중…';
        let success = null;
        try {
          const session = await getSession();
          const response = await fetch('/api/sports/slips/submit/', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': session.csrfToken}, body: JSON.stringify({...body, requestId: attempt.requestId})});
          const result = await response.json();
          if (!response.ok || !result.ok) throw new Error(result.message || '접수하지 못했습니다.');
          success = result.slip;
          window.dispatchEvent(new Event('wallet-changed'));
          sportsSlip.picks.clear(); sportsSlip.stake = ''; sportsSlip.pending = null;
        } catch (error) {cartNotice.textContent = error.message || '연결을 확인하고 다시 눌러 주세요.';}
        finally {sportsSlip.submitting = false; panel.inert = false; submit.removeAttribute('aria-busy'); submit.textContent = '배팅하기'; quoteRefresh();}
        if (success) {
          await refreshFunds();
          cartNotice.textContent = '#' + success.id + ' 테스트 접수 완료 · 가상머니 ' + format(success.totalStake) + ' 차감';
        }
      };
      historyBox.replaceChildren();
      async function history(page = 1) {
        if (!wallet) return;
        const version = ++historyVersion;
        try {
          const response = await fetch('/api/sports/slips/?page=' + page, {credentials: 'same-origin', cache: 'no-store'});
          if (!response.ok || !historyBox.isConnected || version !== historyVersion) return;
          const result = await response.json(); historyBox.replaceChildren(make('h3', '배팅 내역'));
          if (!result.items.length) historyBox.append(make('p', '접수 내역이 없습니다.'));
          const resultLabel = {pending: '정산 대기', won: '적중', lost: '미적중', void: '취소', mixed: '혼합 결과'};
          for (const item of result.items) {
            const row = make('article', '', 'sb-history-ticket'); row.dataset.slipId=item.id;
            const heading=make('div','','sb-ticket-heading');heading.append(make('strong','#'+item.id+' · '+(item.mode==='single'?'싱글':'멀티')+' · '+(resultLabel[item.status]||'정산 대기')),make('small',time(item.createdAt)));row.append(heading);
            const scroll=make('div','','sb-ticket-scroll'),table=make('table'),thead=make('thead'),header=make('tr');
            for(const label of ['경기 시간','리그','홈팀','배당','기준값','배당','원정팀','결과'])header.append(make('th',label));thead.append(header);table.append(thead);
            const tbody=make('tbody');
            for (const leg of item.legs) tbody.append(sportsHistoryRow(leg,make,time,priceText,marketName(leg.market)));
            table.append(tbody);scroll.append(table);row.append(scroll);
            const totals=make('dl','','sb-ticket-totals');
            const odds=item.mode==='multi'?priceText(item.legs.reduce((value,leg)=>value*Number(leg.price),1)):item.legs.map(leg=>priceText(leg.price)).join(' / ');
            for(const [label,value] of [['배당',odds],['배팅금액',format(item.totalStake)+'원'],['적중예상금액',format(item.expectedReturn||0)+'원'],['적중금액',format(item.creditedAmount||0)+'원']]){const cell=make('div');cell.append(make('dt',label),make('dd',value));totals.append(cell);}row.append(totals);
            historyBox.append(row);
          }
          for (const [label, target] of [['이전', result.page - 1], ['다음', result.page + 1]]) {
            const button = make('button', label); button.type = 'button'; button.disabled = target < 1 || target > result.pages; button.onclick = () => history(target); historyBox.append(button);
          }
        } catch {if (historyBox.isConnected && version === historyVersion) historyBox.textContent = '접수 내역을 불러오지 못했습니다.';}
      }
      history();
      quoteRefresh = () => {
        const stake = stakeValue(); const choices = [...sportsSlip.picks.values()];
        submit.disabled = sportsSlip.submitting || !wallet || !choices.length || stake <= 0n;
        availabilityNote.textContent = !wallet ? '로그인 후 이용할 수 있습니다.' : !choices.length ? '경기 배당을 먼저 선택해 주세요.' : stake <= 0n ? '금액을 입력해 주세요.' : '';
        submit.title = availabilityNote.textContent;
        let numerator = 1n, denominator = 1n, winnings = 0n;
        for (const pick of choices) {
          const [whole, fraction = ''] = pick.outcome.price.split('.');
          const odd = BigInt(whole) * 10000n + BigInt((fraction + '0000').slice(0, 4));
          numerator *= odd; denominator *= 10000n; winnings += stake * odd / 10000n;
        }
        const combined = numerator * 10000n / denominator;
        multiplier.textContent = sportsSlip.mode === 'single' ? choices.length + '개 싱글' : 'x ' + format(combined / 10000n) + '.' + String(combined % 10000n).padStart(4, '0');
        outlay.textContent = format(sportsSlip.mode === 'single' ? stake * BigInt(choices.length) : choices.length ? stake : 0n) + '원';
        const expected = !choices.length ? 0n : sportsSlip.mode === 'single' ? winnings : stake * numerator / denominator;
        payout.textContent = format(expected) + '원';
        if (stake > 1000000000000n) cartNotice.textContent = '입력 한도는 1조 원입니다.';
        if (limits) {const prefix = sportsSlip.mode === 'single' ? 'single' : 'multi'; limitsNote.textContent = '한도 ' + format(limits[prefix + '_min']) + ' ~ ' + format(limits[prefix + '_max']) + '원 · 최대 당첨 ' + format(limits[prefix + '_payout']) + '원';}
      };
      quoteRefresh();
    }
    async function refreshFunds() {
      const owner = document.querySelector('.header-sub>div')?.dataset.username || '';
      if (sportsSlip.owner !== null && sportsSlip.owner !== owner) {sportsSlip.picks.clear(); sportsSlip.stake = ''; sportsSlip.pending = null;}
      sportsSlip.owner = owner;
      try {
        const [walletResponse, detailsResponse, permissionsResponse] = await Promise.all([fetch('/api/wallet/', {cache: 'no-store', credentials: 'same-origin'}), fetch('/api/accounts/details/', {cache: 'no-store', credentials: 'same-origin'}), fetch('/api/sports/permissions/', {cache: 'no-store', credentials: 'same-origin'})]);
        data.canLoadExtra = permissionsResponse.ok && (await permissionsResponse.json()).canLoadExtra;
        wallet = walletResponse.ok ? await walletResponse.json() : null;
        limits = detailsResponse.ok ? (await detailsResponse.json()).limits : null; cash = BigInt(wallet?.available || 0);
      } catch {wallet = null; limits = null; cash = 0n;}
      if (valid()) {renderCart(); renderDetail(); updateSelections();}
    }
    activeSportsFundsRefresh = refreshFunds;
    search.oninput = () => {page = 1; renderList();}; league.onchange = () => {page = 1; renderList();}; sort.onchange = () => {page = 1; renderList();};
    buildGroups(); buildLeagues(); renderList(); renderCart(); await refreshFunds();
  } catch (error) {
    if (valid()) panel.replaceChildren(make('p', error.message || '경기·배당을 불러오지 못했습니다.', 'empty-state'));
  }
}

window.addEventListener('account-changed', () => {
  if (['#/sports', '#/inplay', '#/esports'].includes(location.hash) && activeSportsFundsRefresh) activeSportsFundsRefresh();
});
