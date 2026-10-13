const games = [
  ['파워볼', 'POWERBALL', '🎱', '#198daf35'], ['사다리', 'LADDER', '🪜', '#d59a4535'],
  ['카드 게임', 'CARD GAME', '♠', '#dcb45335'], ['토큰 게임', 'TOKEN GAME', '🪙', '#379e9b35'],
  ['가상 스포츠', 'VIRTUAL SPORTS', '⚽', '#6fa34a35'], ['테이블 게임', 'TABLE GAME', '🃏', '#b8606135'],
  ['골든볼', 'GOLDEN BALL', '🔮', '#a46dd335'], ['파워 사다리', 'POWER LADDER', '🪜', '#e76d5135'],
  ['스타 사다리', 'STAR LADDER', '⭐', '#7698cc35'], ['스타 파워볼', 'STAR POWERBALL', '🎱', '#d3af4535'],
  ['홀덤', 'HOLDEM', '♣', '#977fcb35'], ['넥스트 게임', 'NEXT GAME', '🎲', '#658cb035']
];
const grid = document.querySelector('#game-grid');
games.forEach(([name, english, symbol, glow]) => {
  const card = document.createElement('button');
  card.className = 'game-card';
  card.innerHTML = `<span class="game-tile" style="--glow:${glow}"><span class="game-mark">EVE</span><span class="game-symbol" aria-hidden="true">${symbol}</span><strong>${name}</strong></span><span class="game-label">${english}</span>`;
  card.addEventListener('click', () => showInfo(name, '선택한 게임의 상세 화면은 다음 제작 단계에서 구성합니다. 현재는 메인 화면 디자인을 확인하는 시안입니다.'));
  grid.append(card);
});
function updateClock() {
  document.querySelector('#clock').textContent = '◷ ' + new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', dateStyle: 'medium', timeStyle: 'medium'}).format(new Date());
}
updateClock();
setInterval(updateClock, 1000);
const promos = [
  ['WELCOME EVENT', '새로운 시작, 특별한 혜택', '매일 새로운 이벤트를 만나보세요.', '🎁'],
  ['DAILY EVENT', '오늘의 플레이, 오늘의 즐거움', '일상에 즐거운 순간을 더하세요.', '🏆'],
  ['QUIZ EVENT', '함께 즐기는 퀴즈 이벤트', '새로운 퀴즈와 재미있는 이야기를 만나보세요.', '💡'],
  ['COMMUNITY EVENT', '함께 만드는 특별한 순간', '다양한 소식과 이벤트를 확인하세요.', '🎉']
];
let slide = 0;
const dots = [...document.querySelectorAll('.slide-dots button')];
function setSlide(index) {
  slide = (index + promos.length) % promos.length;
  const [tag, title, description, symbol] = promos[slide];
  document.querySelector('#promo-tag').textContent = tag;
  document.querySelector('#promo-title').textContent = title;
  document.querySelector('#promo-description').textContent = description;
  document.querySelector('.promo-art').textContent = symbol;
  dots.forEach((dot, i) => {dot.classList.toggle('selected', i === slide); dot.setAttribute('aria-pressed', String(i === slide));});
}
document.querySelector('.prev').addEventListener('click', () => setSlide(slide - 1));
document.querySelector('.next').addEventListener('click', () => setSlide(slide + 1));
dots.forEach((dot, i) => dot.addEventListener('click', () => setSlide(i)));
setSlide(0);
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
  dialog.addEventListener('click', event => {if (event.target === dialog) {const rect = dialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();}});
  dialog.addEventListener('close', () => dialog.querySelector('form')?.reset());
});
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', event => {
  event.preventDefault();
  form.reset();
  showInfo('화면 시안 안내', '이 시안은 실제 로그인이나 회원가입을 처리하지 않습니다. 입력한 내용은 저장하거나 전송하지 않았습니다.');
}));
document.querySelectorAll('nav a').forEach(link => link.addEventListener('click', () => {
  document.querySelectorAll('nav a').forEach(item => item.classList.remove('active'));
  link.classList.add('active');
}));
document.querySelector('.promo-detail').addEventListener('click', () => showInfo(promos[slide][1], promos[slide][2] + ' 이벤트 상세 화면은 다음 단계에서 구성합니다.'));
document.querySelector('#all-events').addEventListener('click', () => showInfo('프로모션', promos.map(item => item[1]).join(' · ')));
