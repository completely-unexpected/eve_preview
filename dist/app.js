// Browser-only prototype: no remote API, account storage, or financial transactions.
const games = [
  ['powerball', '파워볼', 'POWERBALL', '🎱', '#198daf35', 'ball'],
  ['ladder', '사다리', 'LADDER', '🪜', '#d59a4535', 'ladder'],
  ['cards', '카드 게임', 'CARD GAME', '♠', '#dcb45335', 'cards'],
  ['token', '토큰 게임', 'TOKEN GAME', '🪙', '#379e9b35', 'ball'],
  ['virtual', '가상 스포츠', 'VIRTUAL SPORTS', '⚽', '#6fa34a35', 'sports'],
  ['table', '테이블 게임', 'TABLE GAME', '🃏', '#b8606135', 'cards'],
  ['golden', '골든볼', 'GOLDEN BALL', '🔮', '#a46dd335', 'ball'],
  ['powerladder', '파워 사다리', 'POWER LADDER', '🪜', '#e76d5135', 'ladder'],
  ['starladder', '스타 사다리', 'STAR LADDER', '⭐', '#7698cc35', 'ladder'],
  ['starball', '스타 파워볼', 'STAR POWERBALL', '🎱', '#d3af4535', 'ball'],
  ['holdem', '홀덤', 'HOLDEM', '♣', '#977fcb35', 'cards'],
  ['next', '넥스트 게임', 'NEXT GAME', '🎲', '#658cb035', 'ball']
];
const promos = [
  ['WELCOME EVENT', '새로운 시작, 특별한 혜택', '매일 새로운 이벤트를 만나보세요.', '🎁'],
  ['DAILY EVENT', '오늘의 플레이, 오늘의 즐거움', '일상에 즐거운 순간을 더하세요.', '🏆'],
  ['QUIZ EVENT', '함께 즐기는 퀴즈 이벤트', '새로운 퀴즈와 재미있는 이야기를 만나보세요.', '💡'],
  ['COMMUNITY EVENT', '함께 만드는 특별한 순간', '다양한 소식과 이벤트를 확인하세요.', '🎉']
];
const main = document.querySelector('main');
const home = document.createElement('div');
home.id = 'home-view';
while (main.firstChild) home.append(main.firstChild);
main.append(home);
const routeView = document.createElement('section');
routeView.className = 'route-view content';
routeView.hidden = true;
main.append(routeView);
const menuRoutes = { SPORTS: 'sports', INPLAY: 'inplay', ESPORTS: 'esports', CASINO: 'casino', GAMES: 'games', EVENTS: 'events', NOTICES: 'notices' };
document.querySelectorAll('nav a').forEach(link => link.href = '#/' + menuRoutes[link.dataset.section]);
document.querySelectorAll('a.logo').forEach(link => link.href = '#/home');
document.querySelector('.hero-button').href = '#/games';
function mapLinks(selector, routes) {
  document.querySelectorAll(selector).forEach((link, i) => link.href = '#/' + routes[i]);
}
mapLinks('.shortcuts a', ['sports', 'inplay', 'esports', 'casino']);
mapLinks('.feature-strip a', ['sports', 'inplay', 'casino', 'events']);
mapLinks('.category-card', ['sports', 'inplay', 'esports', 'casino']);
function gameCard(game) {
  const [id, name, english, symbol, glow] = game;
  return `<a class="game-card" href="#/games/${id}"><span class="game-tile" style="--glow:${glow}"><span class="game-mark">EVE</span><span class="game-symbol" aria-hidden="true">${symbol}</span><strong>${name}</strong></span><span class="game-label">${english}</span></a>`;
}
document.querySelector('#game-grid').innerHTML = games.map(gameCard).join('');
function updateClock() {
  document.querySelector('#clock').textContent = '◷ ' + new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', dateStyle: 'medium', timeStyle: 'medium' }).format(new Date());
}
updateClock();
setInterval(updateClock, 1000);
let slide = 0;
const dots = [...document.querySelectorAll('.slide-dots button')];
function setSlide(index) {
  slide = (index + promos.length) % promos.length;
  const [tag, title, description, symbol] = promos[slide];
  document.querySelector('#promo-tag').textContent = tag;
  document.querySelector('#promo-title').textContent = title;
  document.querySelector('#promo-description').textContent = description;
  document.querySelector('.promo-art').textContent = symbol;
  dots.forEach((dot, i) => {
    dot.classList.toggle('selected', i === slide);
    dot.setAttribute('aria-pressed', String(i === slide));
  });
}
document.querySelector('.prev').addEventListener('click', () => setSlide(slide - 1));
document.querySelector('.next').addEventListener('click', () => setSlide(slide + 1));
dots.forEach((dot, i) => dot.addEventListener('click', () => setSlide(i)));
setSlide(0);
document.querySelector('.promo-detail').addEventListener('click', () => location.hash = '#/events/' + slide);
document.querySelector('#all-events').addEventListener('click', () => location.hash = '#/events');
function openDialog(id) {
  document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
  document.querySelector('#' + id).showModal();
}
function showInfo(title, description) {
  document.querySelector('#info-title').textContent = title;
  document.querySelector('#info-description').textContent = description;
  openDialog('info');
}
document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => openDialog(button.dataset.open)));
document.querySelectorAll('.modal-close,.modal-close-action').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => dialog.querySelector('form')?.reset());
});
// Real account form submissions are handled in auth.js.
function pageHeading(title, description, back = 'home', backLabel = '홈으로') {
  return `<a class="back-link" href="#/${back}">← ${backLabel}</a><div class="route-heading"><h1 tabindex="-1">${title}</h1><p>${description}</p></div>`;
}
function emptyMessage() { return '<p class="empty-state" role="status">조건에 맞는 항목이 없습니다. 검색어나 필터를 바꿔 주세요.</p>'; }
function renderGames() {
  routeView.innerHTML = pageHeading('게임 목록', '원하는 게임을 검색하거나 종류별로 찾아보세요.') +
    '<div class="route-tools"><label>게임 검색<input id="game-search" type="search" placeholder="게임 이름을 입력하세요"></label><label>종류<select id="game-type"><option value="all">전체</option><option value="ball">볼 게임</option><option value="ladder">사다리</option><option value="cards">카드 게임</option><option value="sports">스포츠</option></select></label></div><p id="game-count" class="muted" aria-live="polite"></p><div class="game-grid route-game-grid" id="filtered-games"></div>';
  function filter() {
    const query = document.querySelector('#game-search').value.trim().toLowerCase();
    const kind = document.querySelector('#game-type').value;
    const filtered = games.filter(game => (kind === 'all' || game[5] === kind) && (game[1] + ' ' + game[2]).toLowerCase().includes(query));
    document.querySelector('#game-count').textContent = filtered.length + '개의 게임';
    document.querySelector('#filtered-games').innerHTML = filtered.length ? filtered.map(gameCard).join('') : emptyMessage();
  }
  document.querySelector('#game-search').addEventListener('input', filter);
  document.querySelector('#game-type').addEventListener('change', filter);
  filter();
}
function renderGame(id) {
  const game = games.find(item => item[0] === id);
  if (!game) return renderNotFound();
  const [, name, english, symbol] = game;
  routeView.innerHTML = pageHeading(name, english, 'games', '게임 목록으로') + `<div class="detail-panel game-detail"><div class="detail-symbol" aria-hidden="true">${symbol}</div><h2>${name}</h2><p>게임 목록에서 선택한 게임의 상세 화면입니다.</p><div class="sample-notice">게임 API가 아직 연결되지 않았습니다. 실제 게임 실행은 제공하지 않습니다.</div><button class="primary-button" id="game-information">게임 이용 안내</button><a class="secondary-button" href="#/games">다른 게임 보기</a></div>`;
  document.querySelector('#game-information').addEventListener('click', () => showInfo(name + ' 이용 안내', '게임 제공업체 API 연동 후 이 화면에서 게임을 실행할 수 있도록 연결할 예정입니다. 현재는 게임 선택과 화면 이동만 제공됩니다.'));
}
function eventCards() {
  return promos.map(([tag, title, description, symbol], i) => `<a class="event-card detail-panel" href="#/events/${i}"><span class="event-symbol" aria-hidden="true">${symbol}</span><span class="eyebrow">${tag}</span><h2>${title}</h2><p>${description}</p><span class="gold">상세 보기 →</span></a>`).join('');
}
function renderEvents(id) {
  if (id === undefined) {
    routeView.innerHTML = pageHeading('이벤트', '현재 등록된 시안용 이벤트를 확인하세요.') + '<div class="event-grid">' + eventCards() + '</div>';
    return;
  }
  if (!/^[0-3]$/.test(id)) return renderNotFound();
  const [tag, title, description, symbol] = promos[Number(id)];
  routeView.innerHTML = pageHeading(title, tag, 'events', '이벤트 목록으로') + `<article class="detail-panel event-detail"><span class="event-symbol" aria-hidden="true">${symbol}</span><h2>${title}</h2><p>${description}</p><h3>이벤트 안내</h3><p>이벤트 목록과 상세 화면의 연결을 확인하기 위한 샘플 콘텐츠입니다.</p><h3>진행 상태</h3><p>미운영 · 실제 참여 신청이나 혜택 지급은 제공하지 않습니다.</p><div class="detail-actions"><a class="secondary-button" href="#/events/${(Number(id) + 1) % promos.length}">다음 이벤트 →</a><a class="secondary-button" href="#/events">목록으로</a></div></article>`;
}
const providers = [
  ['live', '라이브 테이블', '♠', 'live'], ['cards', '카드 컬렉션', '🃏', 'live'],
  ['classic', '클래식 테이블', '♣', 'live'], ['dice', '다이스 테이블', '🎲', 'live'],
  ['stars', '스타 슬롯', '⭐', 'slot'], ['gold', '골든 슬롯', '🪙', 'slot'],
  ['treasure', '트레저 슬롯', '💎', 'slot'], ['adventure', '어드벤처 슬롯', '🧭', 'slot']
];
function renderCasino() {
  routeView.innerHTML = pageHeading('카지노', '카테고리와 목록 동작을 확인하는 샘플 화면입니다.') + '<div class="filter-tabs" role="group" aria-label="카지노 종류"><button class="active" data-casino="all">전체</button><button data-casino="live">라이브 카지노</button><button data-casino="slot">슬롯 게임</button></div><div class="event-grid" id="casino-list"></div>';
  function filter(kind) {
    document.querySelector('#casino-list').innerHTML = providers.filter(item => kind === 'all' || item[3] === kind).map(([id, name, symbol, type]) => `<button class="event-card detail-panel" data-provider="${id}"><span class="event-symbol" aria-hidden="true">${symbol}</span><h2>${name}</h2><p>${type === 'live' ? '라이브 카지노' : '슬롯 게임'}</p><span class="gold">이용 안내 →</span></button>`).join('');
    routeView.querySelectorAll('[data-provider]').forEach(button => button.addEventListener('click', () => {
      const provider = providers.find(item => item[0] === button.dataset.provider);
      showInfo(provider[1], '게임 제공업체 API가 아직 연결되지 않았습니다. 현재 카드와 분류는 화면 동작 확인용 샘플입니다.');
    }));
  }
  routeView.querySelectorAll('[data-casino]').forEach(button => button.addEventListener('click', () => {
    routeView.querySelectorAll('[data-casino]').forEach(item => item.classList.toggle('active', item === button));
    filter(button.dataset.casino);
  }));
  filter('all');
}
const fixtures = [
  { id: 'football-1', type: 'football', league: '샘플 축구 리그', home: '한강 FC', away: '오로라 FC', time: '19:00', odds: [2.2, 3.6, 2.88], live: true, score: '1 : 1' },
  { id: 'football-2', type: 'football', league: '샘플 축구 리그', home: '블루 FC', away: '레드 FC', time: '20:00', odds: [1.8, 3.2, 4.1], live: false, score: '—' },
  { id: 'basketball-1', type: 'basketball', league: '샘플 농구 리그', home: '서울 스타즈', away: '부산 웨이브', time: '18:30', odds: [1.7, 2.3], live: true, score: '42 : 38' },
  { id: 'tennis-1', type: 'tennis', league: '샘플 테니스 경기', home: '선수 A', away: '선수 B', time: '21:00', odds: [1.9, 1.9], live: false, score: '—' },
  { id: 'esports-1', type: 'esports', league: '샘플 e스포츠 리그', home: '팀 오리온', away: '팀 루나', time: '19:30', odds: [2.06, 1.73], live: true, score: '1 : 0' },
  { id: 'esports-2', type: 'esports', league: '샘플 e스포츠 리그', home: '팀 노바', away: '팀 코멧', time: '22:00', odds: [1.65, 2.4], live: false, score: '—' }
];
const selection = new Map();
function marketLabels(match) { return match.odds.length === 3 ? ['홈', '무승부', '원정'] : ['홈', '원정']; }
function renderSports(mode) {
  const titles = { sports: '스포츠', inplay: '인플레이', esports: 'E-스포츠' };
  const available = fixtures.filter(match => mode === 'esports' ? match.type === 'esports' : match.type !== 'esports' && (mode !== 'inplay' || match.live));
  const types = mode === 'esports' ? [['esports', 'E-스포츠']] : [['football', '축구'], ['basketball', '농구'], ['tennis', '테니스']];
  routeView.innerHTML = pageHeading(titles[mode], '샘플 경기 데이터입니다. 실제 경기·실시간 정보·베팅 서비스와 연결되지 않았습니다.') + '<div class="route-tools"><label>경기 검색<input id="match-search" type="search" placeholder="팀 또는 리그 이름"></label><label>종목<select id="match-type"><option value="all">전체</option>' + types.map(([id, name]) => `<option value="${id}">${name}</option>`).join('') + '</select></label></div><div class="sports-layout"><div><p id="match-count" class="muted" aria-live="polite"></p><div id="match-list"></div></div><section class="detail-panel" id="match-detail" aria-label="경기 상세"></section><aside class="detail-panel selection-panel"><h2>선택 목록</h2><p class="small muted">화면 동작 확인용 · 주문·베팅되지 않습니다</p><div id="selection-list"></div><button class="secondary-button" id="clear-selection">모두 비우기</button></aside></div>';
  function showMatch(match) {
    const panel = document.querySelector('#match-detail');
    panel.innerHTML = `<span class="eyebrow">${match.live ? '샘플 진행 중' : '샘플 예정 경기'}</span><h2>${match.home}<br><span class="muted">vs</span><br>${match.away}</h2><p>${match.league} · ${match.time}</p>${mode === 'inplay' ? `<p class="sample-score">${match.score}</p>` : ''}<h3>선택 항목</h3><div class="odds-list">` + match.odds.map((odd, index) => `<button class="market-button" data-market="${index}" aria-pressed="false"><span>${marketLabels(match)[index]}</span><strong>${odd.toFixed(2)}</strong></button>`).join('') + '</div><p class="small muted">수치는 고정 샘플이며 실시간으로 갱신되지 않습니다.</p>';
    function refreshMarketStates() {
      panel.querySelectorAll('[data-market]').forEach(button => button.setAttribute('aria-pressed', String(selection.has(match.id + ':' + button.dataset.market))));
    }
    panel.querySelectorAll('[data-market]').forEach(button => button.addEventListener('click', () => {
      const index = Number(button.dataset.market);
      const key = match.id + ':' + index;
      if (selection.has(key)) selection.delete(key);
      else selection.set(key, { match, label: marketLabels(match)[index], odd: match.odds[index] });
      renderSelection();
      refreshMarketStates();
    }));
    refreshMarketStates();
  }
  function renderSelection() {
    const list = document.querySelector('#selection-list');
    list.innerHTML = selection.size ? [...selection].map(([key, item]) => `<div class="selection-item"><strong>${item.match.home} vs ${item.match.away}</strong><span>${item.label} · ${item.odd.toFixed(2)}</span><button class="text-button gold" data-remove="${key}" aria-label="${item.match.home} 선택 삭제">삭제</button></div>`).join('') : '<p class="empty-state">선택 목록이 비어 있습니다.</p>';
    list.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => {
      selection.delete(button.dataset.remove);
      renderSelection();
      routeView.querySelectorAll('[data-market]').forEach(item => {
        // Refresh the selected match via its current detail key.
        const match = fixtures.find(fixture => fixture.id === document.querySelector('#match-detail').dataset.matchId);
        if (match) item.setAttribute('aria-pressed', String(selection.has(match.id + ':' + item.dataset.market)));
      });
    }));
  }
  function openMatch(match) {
    document.querySelector('#match-detail').dataset.matchId = match.id;
    showMatch(match);
  }
  function filter() {
    const query = document.querySelector('#match-search').value.trim().toLowerCase();
    const type = document.querySelector('#match-type').value;
    const filtered = available.filter(match => (type === 'all' || match.type === type) && (match.home + match.away + match.league).toLowerCase().includes(query));
    document.querySelector('#match-count').textContent = filtered.length + '개의 샘플 경기';
    document.querySelector('#match-list').innerHTML = filtered.length ? filtered.map(match => `<button class="match-row" data-match="${match.id}"><span class="small muted">${match.league} · ${match.time}</span><strong>${match.home} vs ${match.away}</strong><span class="gold">${mode === 'inplay' ? match.score : '상세 보기 →'}</span></button>`).join('') : emptyMessage();
    routeView.querySelectorAll('[data-match]').forEach(button => button.addEventListener('click', () => openMatch(fixtures.find(match => match.id === button.dataset.match))));
    if (filtered.length) openMatch(filtered[0]);
    else document.querySelector('#match-detail').innerHTML = emptyMessage();
  }
  document.querySelector('#match-search').addEventListener('input', filter);
  document.querySelector('#match-type').addEventListener('change', filter);
  document.querySelector('#clear-selection').addEventListener('click', () => {
    selection.clear();
    renderSelection();
    routeView.querySelectorAll('[data-market]').forEach(button => button.setAttribute('aria-pressed', 'false'));
  });
  filter();
  renderSelection();
}
async function renderNotices(id) {
  const currentHash = location.hash;
  routeView.innerHTML = pageHeading('공지사항', '사이트 소식과 이용 안내를 확인하세요.') + '<div id="notice-content" class="detail-panel" aria-live="polite">불러오는 중…</div>';
  const panel = routeView.querySelector('#notice-content');
  const listing = id === undefined;
  if (!listing && !/^[1-9][0-9]*$/.test(id)) {panel.textContent = '공지사항을 찾을 수 없습니다.'; return;}
  const page = new URLSearchParams(location.search).get('noticePage') || '1';
  try {
    const response = await fetch('/api/notices/' + (listing ? '?page=' + encodeURIComponent(page) : id + '/'), {cache:'no-store', mode:'same-origin'});
    if (location.hash !== currentHash || !panel.isConnected) return;
    if (response.status === 404) {panel.textContent = '공지사항을 찾을 수 없습니다.'; return;}
    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error();
    const result = await response.json();
    if (location.hash !== currentHash || !panel.isConnected) return;
    panel.replaceChildren();
    const date = value => new Intl.DateTimeFormat('ko-KR', {timeZone:'Asia/Seoul',dateStyle:'medium'}).format(new Date(value));
    if (listing) {
      if (!result.items.length) {panel.textContent = '등록된 공지사항이 없습니다.'; return;}
      for (const notice of result.items) {
        const link = document.createElement('a');link.className = 'notice-row';link.href = '#/notices/' + notice.id;
        const title = document.createElement('strong');title.textContent = (notice.pinned ? '[고정] ' : '') + notice.title;
        const time = document.createElement('time');time.dateTime = notice.createdAt;time.textContent = date(notice.createdAt);
        link.append(title,time);panel.append(link);
      }
      const pagination = document.createElement('div');pagination.className = 'detail-actions';
      for (const [number,label] of [[result.page-1,'이전'],[result.page+1,'다음']]) {
        if (number < 1 || number > result.pages) continue;
        const link = document.createElement('a');link.className = 'secondary-button';link.textContent = label;link.href = '?noticePage=' + number + '#/notices';pagination.append(link);
      }
      panel.append(pagination);
    } else {
      const notice = result.notice;
      const title = document.createElement('h2');title.textContent = notice.title;
      const time = document.createElement('p');time.className = 'muted';time.textContent = '작성일 ' + date(notice.createdAt);
      const body = document.createElement('div');body.className = 'notice-body';body.textContent = notice.body;
      const back = document.createElement('a');back.className = 'secondary-button';back.href = '#/notices';back.textContent = '목록으로';
      panel.append(title,time,body,back);
    }
  } catch {if (panel.isConnected) panel.textContent = '공지사항을 불러오지 못했습니다. 새로고침하여 다시 시도해 주세요.';}
}
function renderNotFound() {
  routeView.innerHTML = pageHeading('페이지를 찾을 수 없습니다', '메뉴에서 원하는 화면을 다시 선택해 주세요.') + '<a class="primary-button" href="#/home">홈으로 돌아가기</a>';
}
function route() {
  const parts = location.hash.replace(/^#\/?/, '').split('/');
  const page = parts[0] || 'home';
  const detail = parts[1];
  document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
  home.hidden = page !== 'home';
  routeView.hidden = page === 'home';
  document.querySelectorAll('nav a').forEach(link => {
    const active = menuRoutes[link.dataset.section] === page;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  if (page !== 'home') {
    if (parts.length > 2) renderNotFound();
    else if (page === 'games') detail === undefined ? renderGames() : renderGame(detail);
    else if (page === 'events') renderEvents(detail);
    else if (page === 'notices') renderNotices(detail);
    else if (page === 'casino' && detail === undefined) renderCasino();
    else if (['sports', 'inplay', 'esports'].includes(page) && detail === undefined) renderSports(page);
    else renderNotFound();
  }
  const title = routeView.querySelector('.route-heading h1')?.textContent;
  document.title = page === 'home' ? 'EVE — 메인 화면 시안' : `${title || 'EVE'} — EVE`;
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (page !== 'home') routeView.querySelector('.route-heading h1')?.focus({ preventScroll: true });
}
window.addEventListener('hashchange', route);
route();
