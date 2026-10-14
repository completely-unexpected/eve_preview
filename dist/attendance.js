let attendancePageRequest = 0;

async function renderAttendance(id) {
  const requestId = ++attendancePageRequest;
  const view = document.querySelector('.route-view');
  view.innerHTML = pageHeading('출석체크', '매일 출석하고 보유 포인트를 적립하세요.') +
    '<div id="attendance-content" aria-live="polite">불러오는 중…</div>';
  const panel = view.querySelector('#attendance-content');
  const valid = () => requestId === attendancePageRequest && panel.isConnected;
  const make = (tag, text = '', className = '') => {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const format = value => new Intl.NumberFormat('ko-KR').format(value);
  if (id !== undefined) {panel.textContent = '페이지를 찾을 수 없습니다.'; return;}
  function loginPrompt() {
    panel.replaceChildren(make('p', '로그인 후 출석체크를 이용해 주세요.'));
    const button = make('button', '로그인', 'primary-button');
    button.type = 'button';
    button.onclick = () => openDialog('login');
    panel.append(button);
  }
  try {
    const selected = new URLSearchParams(location.search).get('attendanceMonth');
    const query = new URLSearchParams();
    if (selected) {
      const match = selected.match(/^(\d{4})-(\d{2})$/);
      if (!match) throw new Error('잘못된 조회 월입니다.');
      query.set('year', match[1]); query.set('month', match[2]);
    }
    const response = await fetch('/api/attendance/?' + query.toString(), {cache: 'no-store', credentials: 'same-origin'});
    if (!valid()) return;
    if (response.status === 401) {loginPrompt(); return;}
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '출석 정보를 불러오지 못했습니다.');
    panel.replaceChildren();
    const rules = data.rules;
    const card = make('section', '', 'wallet-panel attendance-panel');
    card.append(make('h2', '출석 안내', 'wallet-panel-title'));
    const notice = make('div', '', 'attendance-rules');
    const lines = [
      ['당일 승인된 입금 원금 합계 ', format(rules.minimumDeposit) + '원', ' 이상이면 출석체크가 가능합니다.'],
      ['매일 출석체크 시 ', format(rules.dailyPoints) + 'P', '가 지급됩니다.'],
      [rules.streakDays + '일 연속 출석 시 ', format(rules.streakPoints) + 'P', '가 지급됩니다. (월 1회)'],
      ['연속 출석과 관계없이 월 ' + rules.monthlyDays + '일 출석 시 ', format(rules.monthlyPoints) + 'P', '가 지급됩니다. (월 1회)']
    ];
    for (const [before, points, after] of lines) {
      const line = make('p');
      line.append(document.createTextNode(before), make('strong', points), document.createTextNode(after));
      notice.append(line);
    }
    notice.append(make('p', '한국 시간 기준 · 매월 연속·누적 출석은 새로 계산됩니다.', 'attendance-time-note'));
    card.append(notice);
    const action = make('div', '', 'attendance-action');
    const status = make('p', data.message, 'attendance-status');
    const submit = make('button', data.checkedToday ? '오늘 출석 완료' : '출석체크', 'primary-button');
    submit.type = 'button';
    submit.disabled = !data.eligible;
    action.append(status, submit);
    card.append(action);
    const feedback = make('p', '', 'wallet-feedback attendance-feedback');
    feedback.setAttribute('role', 'alert');
    feedback.hidden = true;
    card.append(feedback);
    panel.append(card);
    const stats = make('div', '', 'wallet-balances attendance-stats');
    for (const [label, value] of [
      ['조회 월 출석', data.monthlyCount + '일'], ['조회 월 최장 연속 출석', data.longestStreak + '일'], ['조회 월 지급 포인트', format(data.monthlyPoints) + 'P']
    ]) {
      const block = make('div', '', 'wallet-balance');
      block.append(make('span', label), make('strong', value));
      stats.append(block);
    }
    panel.append(stats);
    const calendarPanel = make('section', '', 'wallet-panel attendance-calendar-panel');
    const navigation = make('div', '', 'attendance-month-nav');
    const monthUrl = (year, month) => {
      const url = new URL(location.href);
      url.searchParams.set('attendanceMonth', year + '-' + String(month).padStart(2, '0'));
      url.hash = '/attendance';
      return url.pathname + url.search + url.hash;
    };
    const previous = new Date(Date.UTC(data.year, data.month - 2, 1));
    const next = new Date(Date.UTC(data.year, data.month, 1));
    for (const [target, label] of [[previous, '이전 달'], [next, '다음 달']]) {
      const link = make('a', target === previous ? '‹' : '›', 'attendance-month-arrow');
      link.setAttribute('aria-label', label);
      link.href = monthUrl(target.getUTCFullYear(), target.getUTCMonth() + 1);
      if (target.getUTCFullYear() < 2000 || target.getUTCFullYear() > 2100) {
        link.removeAttribute('href'); link.setAttribute('aria-disabled', 'true');
      }
      if (target === previous) navigation.append(link);
      else {
        navigation.append(make('h2', data.year + '년 ' + data.month + '월'));
        navigation.append(link);
      }
    }
    const current = make('a', '이번 달', 'secondary-button attendance-current-month');
    current.href = monthUrl(Number(data.today.slice(0, 4)), Number(data.today.slice(5, 7)));
    navigation.append(current);
    calendarPanel.append(navigation);
    const calendar = make('div', '', 'attendance-calendar');
    calendar.setAttribute('aria-label', data.year + '년 ' + data.month + '월 출석 달력');
    for (const [index, label] of ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'].entries()) {
      calendar.append(make('div', label, 'attendance-weekday ' + (index === 0 ? 'sunday' : index === 6 ? 'saturday' : '')));
    }
    const firstWeekday = new Date(Date.UTC(data.year, data.month - 1, 1)).getUTCDay();
    const days = new Date(Date.UTC(data.year, data.month, 0)).getUTCDate();
    const recorded = new Map(data.days.map(item => [item.date, item]));
    const cells = Math.ceil((firstWeekday + days) / 7) * 7;
    let pending = false;
    const todayButtons = [submit];
    async function checkToday() {
      if (pending || !data.eligible) return;
      pending = true;
      todayButtons.forEach(button => button.disabled = true);
      feedback.hidden = true;
      try {
        const session = await getSession();
        const result = await fetch('/api/attendance/check/', {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': session.csrfToken}});
        const payload = await result.json();
        if (!valid()) return;
        if (result.status === 401) {loginPrompt(); return;}
        if (!result.ok) {
          feedback.textContent = payload.message || '출석체크하지 못했습니다.';
          feedback.hidden = false;
          return;
        }
        await renderAttendance();
        document.querySelector('#attendance-content')?.prepend(make('p', payload.message, 'wallet-success'));
      } catch {
        feedback.textContent = '연결 오류입니다. 다시 시도해 주세요.';
        feedback.hidden = false;
      } finally {
        pending = false;
        todayButtons.forEach(button => button.disabled = !data.eligible);
      }
    }
    submit.onclick = checkToday;
    for (let cellIndex = 0; cellIndex < cells; cellIndex++) {
      const number = cellIndex - firstWeekday + 1;
      const cell = make('div', '', 'attendance-day');
      if (number < 1 || number > days) {cell.classList.add('attendance-blank'); calendar.append(cell); continue;}
      const date = data.year + '-' + String(data.month).padStart(2, '0') + '-' + String(number).padStart(2, '0');
      cell.dataset.date = date;
      cell.append(make('span', String(number), 'attendance-day-number'));
      if (cellIndex % 7 === 0) cell.classList.add('sunday');
      if (cellIndex % 7 === 6) cell.classList.add('saturday');
      if (date === data.today) {cell.classList.add('attendance-today'); cell.setAttribute('aria-current', 'date');}
      if (recorded.has(date)) {
        cell.append(make('strong', '출석', 'attendance-stamp'));
        cell.title = format(recorded.get(date).points) + 'P 지급';
      } else if (date < data.today) {
        cell.append(make('span', '미출석', 'attendance-absent'));
      } else if (date === data.today) {
        const button = make('button', '체크', 'attendance-cell-check');
        button.type = 'button'; button.disabled = !data.eligible; button.onclick = checkToday;
        todayButtons.push(button); cell.append(button);
      }
      calendar.append(cell);
    }
    calendarPanel.append(calendar);
    panel.append(calendarPanel);
    const history = make('section', '', 'wallet-panel attendance-reward-panel');
    history.append(make('h2', '출석 포인트 지급 내역', 'wallet-panel-title'));
    const list = make('div', '', 'wallet-point-list');
    if (!data.rewards.length) list.append(make('p', '이 달의 출석 포인트 지급 내역이 없습니다.', 'wallet-empty'));
    for (const reward of data.rewards) {
      const row = make('div', '', 'wallet-point-row');
      row.append(make('span', reward.date + ' · ' + reward.kind), make('strong', '+' + format(reward.points) + 'P'));
      list.append(row);
    }
    history.append(list); panel.append(history);
  } catch (error) {
    if (valid()) panel.textContent = error.message || '출석 정보를 불러오지 못했습니다. 새로고침해 주세요.';
  }
}

window.addEventListener('account-changed', () => {
  if (location.hash === '#/attendance') renderAttendance();
});
