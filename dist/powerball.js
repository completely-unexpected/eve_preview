const powerballSlip = {picks: new Map(), stake: '', mode: 'single', pending: null, owner: null, submitting: false};
let stopPowerball = null;

function mountPowerball(panel) {
  const make = (tag, text = '', cls = '') => {const el = document.createElement(tag); el.textContent = text; if (cls) el.className = cls; return el;};
  const fmt = value => new Intl.NumberFormat('ko-KR').format(value);
  const time = value => new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false}).format(new Date(value));
  const labels = {general_parity: '일반볼 홀/짝', general_range: '일반볼 구간', power_parity: '파워볼 홀/짝', power_range: '파워볼 언더/오버'};
  const states = {pending: '정산 대기', won: '적중', lost: '미적중', void: '취소', mixed: '혼합 결과'};
  const layout = make('div', '', 'pb-layout');
  const main = make('div', '', 'pb-main'); const cart = make('aside', '', 'sb-slip pb-cart'); cart.id = 'powerball-cart'; cart.setAttribute('aria-label', '파워볼 배팅 카트');
  // Keep the official broadcast, scale observer and existing source links intact.
  while (panel.firstChild) main.append(panel.firstChild);
  layout.append(main, cart); panel.append(layout);
  const rounds = make('section', '', 'pb-rounds'); rounds.id = 'powerball-rounds'; main.append(rounds);
  const resultBox = make('section', '', 'pb-history'); resultBox.id = 'powerball-results'; main.append(resultBox);
  const historyBox = make('section', '', 'pb-history'); historyBox.id = 'powerball-history'; main.append(historyBox);
  const notice = make('p', '', 'sb-slip-notice');
  let wallet = null, limits = null, cash = 0n, board = null, offset = 0, historyPage = 1, stopped = false, loading = false;
  const valid = () => !stopped && panel.isConnected;
  const now = () => Date.now() + offset;
  const close = event => Date.parse(event.closesAt) <= now();
  const owner = () => document.querySelector('.header-sub>div')?.dataset.username || '';
  let updateQuote = () => {};
  function syncOwner() {
    const current = owner();
    if (powerballSlip.owner !== null && powerballSlip.owner !== current) {powerballSlip.picks.clear(); powerballSlip.stake = ''; powerballSlip.pending = null;}
    powerballSlip.owner = current;
  }
  function selected(event, market, outcome) {
    const old = powerballSlip.picks.get(event.id);
    return old?.market === market.key && old?.outcome.name === outcome.name;
  }
  function highlights() {
    for (const button of rounds.querySelectorAll('[data-round-pick]')) button.setAttribute('aria-pressed', String([...powerballSlip.picks.values()].some(p => button.dataset.roundPick === JSON.stringify([p.event.id, p.market, p.outcome.name]))));
  }
  function buildRounds() {
    rounds.replaceChildren();
    if (!board) {rounds.append(make('p', '회차를 불러오는 중…')); return;}
    rounds.append(make('h3', '회차별 선택'), make('p', '회차당 한 항목을 선택할 수 있습니다. 배당은 화면 예시 기준이며 추첨 30초 전에 마감됩니다.', 'pb-note'));
    for (const event of board.items) {
      const section = make('article', '', 'pb-round'); section.dataset.round = event.id;
      const heading = make('div', '', 'pb-round-heading');
      const timer = make('strong', '', 'pb-timer'); timer.dataset.closes = event.closesAt;
      const refresh = make('button', '새로고침', 'secondary-button'); refresh.type = 'button'; refresh.onclick = () => loadBoard();
      heading.append(make('strong', '● ' + event.round + '회차'), make('span', time(event.startsAt)), timer, refresh); section.append(heading);
      const markets = event.bookmakers[0].markets;
      for (const [title, choices] of [['일반볼 게임', markets.slice(0, 2)], ['파워볼 게임', markets.slice(2)]]) {
        section.append(make('h4', '● ' + title + ' ●'));
        const group = make('div', '', 'pb-market-row');
        for (const market of choices) {
          const field = make('section', '', 'pb-market'); field.append(make('h5', market.title));
          const options = make('div', '', 'pb-options');
          for (const outcome of market.outcomes) {
            const button = make('button', '', 'sb-rate pb-choice'); button.type = 'button'; button.dataset.roundPick = JSON.stringify([event.id, market.key, outcome.name]); button.dataset.closes = event.closesAt;
            button.setAttribute('aria-pressed', String(selected(event, market, outcome)));
            button.append(make('span', outcome.name), make('strong', Number(outcome.price).toFixed(2)));
            button.onclick = () => {
              if (powerballSlip.submitting || close(event)) return;
              if (selected(event, market, outcome)) powerballSlip.picks.delete(event.id);
              else powerballSlip.picks.set(event.id, {event, market: market.key, outcome});
              renderCart(); highlights();
            }; options.append(button);
          }
          field.append(options); group.append(field);
        }
        section.append(group);
      }
      rounds.append(section);
    }
    tick();
  }
  function renderCart() {
    cart.replaceChildren(make('h2', '배팅 카트', 'sb-panel-heading'));
    const tabs = make('div', '', 'sb-slip-tabs');
    for (const [value, name] of [['single', '싱글'], ['multi', '멀티']]) {const button = make('button', name, powerballSlip.mode === value ? 'active' : ''); button.type = 'button'; button.onclick = () => {powerballSlip.mode = value; renderCart();}; tabs.append(button);}
    cart.append(tabs);
    const picks = make('div', '', 'sb-picks');
    if (!powerballSlip.picks.size) picks.append(make('p', '⊖\n배팅 카트가 비어 있습니다.', 'sb-empty-slip'));
    for (const [id, p] of powerballSlip.picks) {
      const row = make('div', '', 'sb-pick'); const remove = make('button', '×', 'sb-remove-pick'); remove.type = 'button'; remove.setAttribute('aria-label', p.event.round + '회차 선택 삭제'); remove.onclick = () => {powerballSlip.picks.delete(id); renderCart(); highlights();};
      row.append(remove, make('strong', p.event.day + ' · ' + p.event.round + '회차'), make('span', labels[p.market] + ' · ' + p.outcome.name), make('b', Number(p.outcome.price).toFixed(2))); picks.append(row);
    }
    const clear = make('button', '▣ 모두 비우기', 'sb-clear-slip'); clear.type = 'button'; clear.onclick = () => {powerballSlip.picks.clear(); renderCart(); highlights();};
    cart.append(picks, notice, clear, make('p', wallet ? '사용 가능 금액 ' + fmt(cash) + '원' : '로그인 후 이용해 주세요.', 'sb-slip-funds'));
    let controls;
    controls = createStakeControls({id: 'powerball-stake', value: powerballSlip.stake, presets: [5000, 10000, 30000, 50000, 100000, 300000, 500000, 1000000],
      onChange: (value, error) => {powerballSlip.stake = value; notice.textContent = error; updateQuote();},
      onMax: () => {if (!wallet) return null; const divisor = powerballSlip.mode === 'single' ? BigInt(Math.max(1, powerballSlip.picks.size)) : 1n; const cap = BigInt(limits?.[powerballSlip.mode + '_max'] || 1000000000000); return cash / divisor < cap ? cash / divisor : cap;}});
    cart.append(controls.root);
    const quote = make('dl', '', 'sb-quote'); const odds = make('dd'); odds.id = 'powerball-odds'; const total = make('dd'); total.id = 'powerball-total-stake'; const expected = make('dd'); expected.id = 'powerball-payout';
    for (const [label, value] of [['전체 배당', odds], ['총 배팅금액', total], ['예상 당첨금액', expected]]) {const row = make('div'); row.append(make('dt', label), value); quote.append(row);}
    const help = make('p', '', 'sb-slip-help'); const limitNote = make('p', '', 'sb-slip-limit');
    const submit = make('button', powerballSlip.submitting ? '접수 중…' : '배팅하기', 'primary-button sb-submit-bet'); submit.type = 'button';
    cart.append(quote, limitNote, make('p', '싱글은 선택 회차마다 금액이 적용됩니다. 멀티는 서로 다른 회차를 조합합니다.', 'sb-slip-help'), help, submit);
    updateQuote = () => {
      const stake = controls.stakeValue(); const choices = [...powerballSlip.picks.values()];
      let product = 1n, denominator = 1n, sum = 0n;
      for (const p of choices) {const odd = BigInt(p.outcome.price.replace('.', '')); product *= odd; denominator *= 10000n; sum += stake * odd / 10000n;}
      const multiplier = product * 10000n / denominator;
      odds.textContent = powerballSlip.mode === 'single' ? choices.length + '개 싱글' : 'x ' + String(multiplier / 10000n) + '.' + String(multiplier % 10000n).padStart(4, '0');
      total.textContent = fmt(choices.length ? stake * (powerballSlip.mode === 'single' ? BigInt(choices.length) : 1n) : 0n) + '원';
      expected.textContent = fmt(!choices.length ? 0n : powerballSlip.mode === 'single' ? sum : stake * product / denominator) + '원';
      help.textContent = !wallet ? '로그인 후 이용할 수 있습니다.' : !choices.length ? '회차와 항목을 선택해 주세요.' : stake <= 0n ? '금액을 입력해 주세요.' : '';
      if (limits) limitNote.textContent = '한도 ' + fmt(limits[powerballSlip.mode + '_min']) + ' ~ ' + fmt(limits[powerballSlip.mode + '_max']) + '원';
      submit.disabled = powerballSlip.submitting || !wallet || !choices.length || stake <= 0n || choices.some(p => close(p.event));
    };
    submit.onclick = async () => {
      if (powerballSlip.submitting || submit.disabled) return;
      const body = {mode: powerballSlip.mode, stake: controls.stakeValue().toString(), picks: [...powerballSlip.picks.values()].map(p => ({eventId: p.event.id, bookKey: 'simulation', market: p.market, ...p.outcome}))};
      const signature = JSON.stringify(body); if (!powerballSlip.pending || powerballSlip.pending.signature !== signature) powerballSlip.pending = {signature, requestId: crypto.randomUUID()};
      const attempt = powerballSlip.pending; const sendingOwner = owner(); powerballSlip.submitting = true; submit.disabled = true; submit.textContent = '접수 중…'; panel.inert = true;
      let success = null;
      try {
        const session = await getSession();
        const response = await fetch('/api/games/powerball/submit/', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': session.csrfToken}, body: JSON.stringify({...body, requestId: attempt.requestId})});
        const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.message || '접수하지 못했습니다.'); success = result.slip;
        if (sendingOwner === owner()) {powerballSlip.picks.clear(); powerballSlip.stake = ''; powerballSlip.pending = null;}
      } catch (e) {if (valid()) notice.textContent = e.message;}
      finally {powerballSlip.submitting = false; panel.inert = false; submit.textContent = '배팅하기'; updateQuote();}
      if (success && valid()) {await funds(); notice.textContent = '#' + success.id + ' 접수 완료 · ' + fmt(success.totalStake) + '원 차감'; await history(1); highlights();}
    };
    updateQuote();
  }
  async function history(page = historyPage) {
    if (!valid()) return;
    if (!wallet) {historyBox.replaceChildren(make('h3', '배팅 내역'), make('p', '로그인 후 본인 내역을 확인할 수 있습니다.')); return;}
    try {
      const response = await fetch('/api/games/powerball/slips/?page=' + page, {credentials: 'same-origin', cache: 'no-store'});
      const result = await response.json(); if (!valid()) return; if (!response.ok) throw new Error(result.message);
      historyPage = result.page; historyBox.replaceChildren(make('h3', '배팅 내역'));
      const scroll = make('div', '', 'pb-history-scroll'); const table = document.createElement('table'); const head = document.createElement('thead'); const titles = make('tr');
      for (const label of ['회차', '배팅시간', '게임분류', '배팅내역', '배당률', '배팅금액', '적중금액', '적중여부']) titles.append(make('th', label)); head.append(titles); table.append(head);
      const tbody = document.createElement('tbody');
      if (!result.items.length) {const row = make('tr'); const cell = make('td', '내역이 없습니다.'); cell.colSpan = 8; row.append(cell); tbody.append(row);}
      for (const slip of result.items) for (const leg of slip.legs) {
        const row = make('tr');
        for (const text of [leg.away, time(slip.createdAt), slip.mode === 'single' ? '싱글' : '멀티 #' + slip.id, (labels[leg.market] || leg.market) + ' · ' + leg.name, Number(leg.price).toFixed(2), fmt(slip.stake), slip.mode === 'multi' ? '접수 합계 ' + fmt(slip.creditedAmount) : leg.result === 'won' ? fmt(BigInt(slip.stake) * BigInt(leg.price.replace('.', '')) / 10000n) : leg.result === 'void' ? fmt(slip.stake) : '0', states[leg.result] || '정산 대기']) row.append(make('td', text));
        tbody.append(row);
      }
      table.append(tbody); scroll.append(table); historyBox.append(scroll);
      const nav = make('div', '', 'sb-pagination');
      for (const [label, target] of [['이전', result.page - 1], ['다음', result.page + 1]]) {const b = make('button', label); b.type = 'button'; b.disabled = target < 1 || target > result.pages; b.onclick = () => history(target); nav.append(b);} historyBox.append(nav);
    } catch (e) {if (valid()) historyBox.textContent = e.message || '내역을 불러오지 못했습니다.';}
  }
  let fundsSignature = null;
  async function funds() {
    syncOwner();
    try {
      const [w, d] = await Promise.all([fetch('/api/wallet/', {credentials: 'same-origin', cache: 'no-store'}), fetch('/api/accounts/details/', {credentials: 'same-origin', cache: 'no-store'})]);
      wallet = w.ok ? await w.json() : null; limits = d.ok ? (await d.json()).limits : null; cash = BigInt(wallet?.available || 0);
    } catch {wallet = null; cash = 0n;}
    if (valid()) {const signature = JSON.stringify([owner(), wallet?.available ?? null, limits]); if (signature !== fundsSignature) {fundsSignature = signature; renderCart();} await history();}
  }
  async function loadBoard() {
    if (loading || !valid() || powerballSlip.submitting) return;
    loading = true;
    try {
      const response = await fetch('/api/games/powerball/board/', {cache: 'no-store', credentials: 'same-origin'}); const data = await response.json();
      if (!valid()) return; if (!response.ok || !data.ok) throw new Error(data.message || '회차 조회 실패');
      board = data;
      resultBox.replaceChildren(make('h3', '공식 회차 결과'));
      const sync = data.resultSync;
      resultBox.append(make('p', sync?.fetchedAt ? '결과 수신 ' + time(sync.fetchedAt) + (sync.error ? ' · 수신 오류: 이전 결과 유지' : '') + (!sync.enabled ? ' · 자동 정산 중지' : '') : '공식 결과를 기다리고 있습니다.', 'pb-note'));
      const values = make('div', '', 'pb-result-list');
      const resultScroll=make('div','','pb-history-scroll'),resultTable=make('table'),head=make('thead'),titles=make('tr');
      for(const label of ['회차','일반볼','합계','일반볼 홀/짝','일반볼 대/중/소','파워볼','파워볼 홀/짝','파워볼 언더/오버'])titles.append(make('th',label));head.append(titles);resultTable.append(head);
      const body=make('tbody');for(const r of data.results||[]){const row=make('tr'),outcomes=r.outcomes||{};for(const value of [r.day+' · '+r.round+'회차',r.balls.join(' · '),r.total??r.balls.reduce((n,v)=>n+v,0),outcomes.general_parity||'',outcomes.general_range||'',r.powerball,outcomes.power_parity||'',outcomes.power_range||''])row.append(make('td',String(value)));body.append(row);}resultTable.append(body);resultScroll.append(resultTable);values.append(resultScroll);
      resultBox.append(values);
      offset = Date.parse(data.serverTime) - Date.now();
      let removed = false;
      for (const [id, pick] of powerballSlip.picks) if (close(pick.event) || !board.items.some(e => e.id === id)) {powerballSlip.picks.delete(id); removed = true;}
      buildRounds(); if (removed) renderCart();
      await funds();
    } catch (e) {if (valid()) notice.textContent = e.message;}
    finally {loading = false;}
  }
  function tick() {
    if (!valid()) return;
    for (const timer of rounds.querySelectorAll('.pb-timer')) {const seconds = Math.max(0, Math.ceil((Date.parse(timer.dataset.closes) - now()) / 1000)); timer.textContent = seconds ? String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0') + ' · 배팅' : '마감';}
    for (const button of rounds.querySelectorAll('.pb-choice')) button.disabled = powerballSlip.submitting || Date.parse(button.dataset.closes) <= now();
    if (powerballSlip.submitting) return;
    let changed = false; for (const [id, p] of powerballSlip.picks) if (close(p.event)) {powerballSlip.picks.delete(id); changed = true;}
    if (changed) {renderCart(); highlights(); notice.textContent = '마감된 회차를 카트에서 제외했습니다.';}
    updateQuote();
  }
  async function accountChanged() {if (valid()) {await funds(); highlights();}}
  document.addEventListener('visibilitychange', visible); function visible() {if (!document.hidden && valid()) {loadBoard(); funds();}}
  window.addEventListener('account-changed', accountChanged);
  const clock = setInterval(tick, 1000); const refresh = setInterval(() => {if (!document.hidden && valid()) loadBoard();}, 30000);
  stopPowerball = () => {stopped = true; clearInterval(clock); clearInterval(refresh); document.removeEventListener('visibilitychange', visible); window.removeEventListener('account-changed', accountChanged);};
  renderCart(); loadBoard(); funds();
}
