const sportsSlip = {picks: new Map(), mode: 'multi', stake: '', owner: null};
let sportsBoardRequest = 0;
let activeSportsFundsRefresh = null;

async function renderSports(mode) {
  const requestId = ++sportsBoardRequest;
  activeSportsFundsRefresh = null;
  const view = document.querySelector('.route-view');
  view.innerHTML = pageHeading(mode === 'inplay' ? '인플레이' : mode === 'esports' ? 'E-스포츠' : '스포츠', '경기·배당 데이터 · The Odds API') + '<div id="sports-board" aria-live="polite">전체 경기·배당을 불러오는 중…</div>';
  const panel = view.querySelector('#sports-board');
  const valid = () => requestId === sportsBoardRequest && panel.isConnected;
  const make = (tag, text = '', cls = '') => {const element = document.createElement(tag); element.textContent = text; if (cls) element.className = cls; return element;};
  const format = value => new Intl.NumberFormat('ko-KR').format(value);
  const priceText = value => Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 4});
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
    meta.append(make('span', data.source + ' · 저장된 배당 조회 ' + time(data.fetchedAt)), make('span', data.items.length + '개 경기 · ' + data.completedLeagues.length + '개 리그'));
    panel.append(meta);
    if (!data.complete) panel.append(make('p', '일부 리그의 조회가 완료되지 않았습니다. 현재 저장된 경기만 표시합니다.', 'wallet-feedback'));
    const eligibleEvents = data.items.filter(event => !event.completed && (mode === 'esports' ? /esport/i.test(event.group + event.leagueKey) : !/esport/i.test(event.group + event.leagueKey)));
    const phaseEvents = eligibleEvents.filter(event => mode === 'inplay' ? event.status === 'live' : event.status !== 'live');
    const groups = [...new Set(data.leagues.filter(league => mode === 'esports' ? /esport/i.test(league.group + league.key) : !/esport/i.test(league.group + league.key)).map(league => league.group))];
    let selectedGroup = groups.includes('Soccer') ? 'Soccer' : groups[0] || 'all';
    let selectedEvent = null;
    let selectedBook = '';
    let marketFilter = 'all';
    let page = 1;
    const layout = make('div', '', 'sb-layout');
    const sidebar = make('aside', '', 'sb-sidebar');
    const center = make('section', '', 'sb-center');
    const detail = make('section', '', 'sb-detail'); detail.id = 'match-detail';
    const cart = make('aside', '', 'sb-slip'); cart.id = 'betting-cart'; cart.setAttribute('aria-label', '베팅 카트');
    layout.append(sidebar, center, detail, cart); panel.append(layout);
    const phases = make('div', '', 'sb-phase-tabs');
    for (const [route, label] of [['sports', 'Prematch'], ['inplay', 'Inplay']]) {const link = make('a', label, route === mode ? 'active' : ''); link.href = '#/' + route; phases.append(link);}
    sidebar.append(phases);
    const groupList = make('div', '', 'sb-group-list'); sidebar.append(groupList);
    const groupTabs = make('div', '', 'sb-group-tabs'); center.append(groupTabs);
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
      button.append(make('span', outcomeLabel(outcome, short, event)), make('strong', priceText(outcome.price)));
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
      groupList.replaceChildren(); groupTabs.replaceChildren();
      for (const group of ['all', ...groups]) {
        const [icon, name] = group === 'all' ? ['▣', '전체'] : groupsInfo[group] || ['●', group];
        const number = phaseEvents.filter(event => group === 'all' || event.group === group).length;
        const button = make('button', '', 'sb-group ' + (selectedGroup === group ? 'active' : '')); button.type = 'button'; button.dataset.group = group;
        button.append(make('span', icon + ' ' + name), make('strong', String(number))); button.onclick = () => setGroup(group); groupList.append(button);
        if (group !== 'all') {const tab = make('button', icon + ' ' + name, selectedGroup === group ? 'active' : ''); tab.type = 'button'; tab.onclick = () => setGroup(group); groupTabs.append(tab);}
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
      for (const event of events.slice((page - 1) * 40, page * 40)) {
        if (lastLeague !== event.leagueKey) {list.append(make('h3', event.league, 'sb-league-heading')); lastLeague = event.leagueKey;}
        const row = make('div', '', 'sb-match-row'); row.dataset.match = event.id;
        const title = make('button', '', 'sb-match-title'); title.type = 'button';
        title.append(make('small', time(event.startsAt) + (event.status === 'live' ? ' · 진행 중' : event.status === 'unconfirmed' ? ' · 진행 상태 미확인' : '')));
        title.append(make('strong', event.home), make('strong', event.away));
        title.onclick = () => {selectedEvent = event; selectedBook = ''; marketFilter = 'all'; renderDetail();}; row.append(title);
        const book = event.bookmakers[0];
        const market = book?.markets.find(item => item.key === 'h2h');
        if (book) row.append(make('span', book.title, 'sb-book-source'));
        const prices = make('div', '', 'sb-main-rates');
        if (market) {
          const outcomes = [...market.outcomes].sort((a, b) => ([event.home, 'Draw', event.away].indexOf(a.name)) - ([event.home, 'Draw', event.away].indexOf(b.name)));
          for (const outcome of outcomes) prices.append(rateButton(event, book, market, outcome, true));
        } else prices.append(make('span', '승무패 배당 미제공', 'sb-no-odds'));
        row.append(prices); list.append(row);
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
        for (const outcome of market.outcomes) outcomes.append(rateButton(event, book, market, outcome));
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
      const amountRow = make('div', '', 'sb-stake-row');
      const input = document.createElement('input'); input.id = 'cart-stake'; input.type = 'text'; input.inputMode = 'numeric'; input.autocomplete = 'off'; input.maxLength = 25; input.placeholder = '베팅금액'; input.setAttribute('aria-label', '베팅금액'); input.value = sportsSlip.stake;
      for (const [symbol, delta] of [['−', -10000n], ['+', 10000n]]) {const button = make('button', symbol); button.type = 'button'; button.setAttribute('aria-label', delta < 0 ? '금액 1만원 줄이기' : '금액 1만원 늘리기'); button.onclick = () => setStake((stakeValue() + delta < 0n ? 0n : stakeValue() + delta).toString()); amountRow.append(button);}
      amountRow.append(input); cart.append(amountRow);
      const presets = make('div', '', 'sb-stake-presets');
      for (const amount of [10000, 50000, 100000, 500000, 1000000]) {const button = make('button', format(amount)); button.type = 'button'; button.onclick = () => setStake(String(amount)); presets.append(button);}
      const maxButton = make('button', 'MAX'); maxButton.type = 'button'; maxButton.onclick = () => {
        if (!wallet) {cartNotice.textContent = '로그인 후 MAX 금액을 사용할 수 있습니다.'; return;}
        const divisor = sportsSlip.mode === 'single' ? BigInt(Math.max(1, sportsSlip.picks.size)) : 1n;
        const limit = limits ? BigInt(limits[sportsSlip.mode === 'single' ? 'single_max' : 'multi_max']) : 1000000000000n;
        setStake((cash / divisor < limit ? cash / divisor : limit).toString());
      }; presets.append(maxButton); cart.append(presets);
      const quote = make('dl', '', 'sb-quote');
      const multiplier = make('dd'); multiplier.id = 'cart-odds'; const outlay = make('dd'); outlay.id = 'cart-total-stake'; const payout = make('dd'); payout.id = 'cart-payout';
      for (const [label, value] of [['전체 배당', multiplier], ['총 베팅금액', outlay], ['예상 당첨금액', payout]]) {const row = make('div'); row.append(make('dt', label), value); quote.append(row);}
      cart.append(quote, make('p', '싱글 금액은 각 경기에 적용됩니다. 한 경기에서는 한 항목만 선택할 수 있습니다.', 'sb-slip-help'));
      const limitsNote = make('p', '', 'sb-slip-limit'); cart.append(limitsNote);
      cart.append(make('p', '선택·예상금액 계산용 카트입니다. 실제 접수 기능은 아직 연결되지 않았습니다.', 'sb-slip-help'));
      const submit = make('button', '베팅 접수 준비 중', 'primary-button sb-submit-bet'); submit.type = 'button'; submit.disabled = true; cart.append(submit);
      function stakeValue() {const digits = input.value.replace(/,/g, ''); return /^\d+$/.test(digits) && digits.length <= 13 ? BigInt(digits) : 0n;}
      function setStake(value) {input.value = value; input.dispatchEvent(new Event('input'));}
      input.oninput = () => {
        const raw = input.value;
        if (!/^[0-9,]*$/.test(raw)) {cartNotice.textContent = '금액은 숫자로 입력해 주세요.'; sportsSlip.stake = raw; quoteRefresh(); return;}
        const before = raw.slice(0, input.selectionStart ?? raw.length).replace(/,/g, '').length;
        const original = raw.replace(/,/g, ''); const digits = original.replace(/^0+(?=\d)/, '');
        input.value = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        let cursor = 0, consumed = 0; const target = Math.max(0, before - (original.length - digits.length));
        while (cursor < input.value.length && consumed < target) {if (input.value[cursor] !== ',') consumed++; cursor++;}
        input.setSelectionRange(cursor, cursor); sportsSlip.stake = input.value; cartNotice.textContent = ''; quoteRefresh();
      };
      quoteRefresh = () => {
        const stake = stakeValue(); const choices = [...sportsSlip.picks.values()];
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
      if (sportsSlip.owner !== null && sportsSlip.owner !== owner) {sportsSlip.picks.clear(); sportsSlip.stake = '';}
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
