let walletActiveAction = 'deposit';

async function renderWallet(id) {
  const view = document.querySelector('.route-view');
  view.innerHTML = pageHeading('입금·출금', '보유금액과 포인트, 신청 내역을 확인하세요.') +
    '<div id="wallet-content" aria-live="polite">불러오는 중…</div>';
  const panel = view.querySelector('#wallet-content');
  if (id !== undefined && id !== 'convert') {
    panel.textContent = '페이지를 찾을 수 없습니다.';
    return;
  }

  if (id === 'convert') walletActiveAction = 'convert';

  const make = (tag, value = '', className = '') => {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    return element;
  };
  const format = value => new Intl.NumberFormat('ko-KR').format(value);
  const dateTime = value => new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false
  }).format(new Date(value));

  function loginPrompt() {
    panel.replaceChildren(make('p', '로그인 후 보유금액과 신청 내역을 확인해 주세요.', 'wallet-login'));
    const button = make('button', '로그인', 'primary-button');
    button.type = 'button';
    button.onclick = () => openDialog('login');
    panel.append(button);
  }

  try {
    const page = new URLSearchParams(location.search).get('walletPage') || '1';
    const response = await fetch('/api/wallet/?page=' + encodeURIComponent(page), {
      cache: 'no-store', credentials: 'same-origin'
    });
    if (!panel.isConnected) return;
    if (response.status === 401) { loginPrompt(); return; }
    if (!response.ok) throw new Error('wallet load failed');
    const data = await response.json();
    panel.replaceChildren();

    const balances = make('div', '', 'wallet-balances');
    for (const [label, value, unit] of [
      ['사용 가능한 보유금액', data.available, '원'],
      ['출금 신청 중', data.reserved, '원'],
      ['보유 포인트', data.points, 'P']
    ]) {
      const block = make('div', '', 'wallet-balance');
      block.append(make('span', label), make('strong', format(value) + unit));
      balances.append(block);
    }
    panel.append(balances);

    const layout = make('div', '', 'wallet-layout');
    const left = make('div', '', 'wallet-column');
    const right = make('div', '', 'wallet-column');
    layout.append(left, right);
    panel.append(layout);

    const notice = make('section', '', 'wallet-panel');
    notice.append(make('h2', '이용 안내', 'wallet-panel-title'));
    const notes = make('div', '', 'wallet-notes');
    for (const line of [
      '입금 신청은 관리자 승인 후 보유금액에 반영됩니다.',
      '출금 신청 금액은 승인 또는 거절될 때까지 별도로 보관됩니다.',
      '포인트는 관리자가 지급하며, 1포인트를 보유금액 1원으로 전환할 수 있습니다.'
    ]) notes.append(make('p', line));
    notice.append(notes);
    left.append(notice);

    const application = make('section', '', 'wallet-panel');
    application.append(make('h2', '신청', 'wallet-panel-title'));
    const tabs = make('div', '', 'wallet-tabs');
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', '신청 종류');
    const formArea = make('div', '', 'wallet-form-area');
    const actions = [
      ['deposit', '입금 신청'],
      ['withdraw', '출금 신청'],
      ['convert', '포인트 전환']
    ];
    for (const [action, label] of actions) {
      const button = make('button', label);
      button.type = 'button';
      button.setAttribute('role', 'tab');
      button.onclick = () => {
        walletActiveAction = action;
        if (location.hash === '#/wallet/convert' && action !== 'convert') {
          window.history.replaceState(window.history.state, '', '#/wallet');
        }
        showForm();
      };
      tabs.append(button);
    }
    application.append(tabs, formArea);
    left.append(application);

    function showForm() {
      [...tabs.children].forEach((button, index) => {
        const selected = actions[index][0] === walletActiveAction;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-selected', String(selected));
      });
      formArea.replaceChildren();
      const action = walletActiveAction;
      const label = actions.find(item => item[0] === action)[1];
      const form = make('form', '', 'wallet-form');
      const row = make('div', '', 'wallet-form-row');
      const inputLabel = make('label', action === 'convert' ? '전환할 포인트' : '신청 금액');
      const input = document.createElement('input');
      input.name = action === 'convert' ? 'points' : 'amount';
      input.type = 'text';
      input.maxLength = 25;
      input.autocomplete = 'off';
      input.inputMode = 'numeric';
      input.placeholder = action === 'convert' ? '포인트를 입력해 주세요' : '금액을 입력해 주세요';
      input.required = true;
      function formatInput() {
        const raw = input.value;
        if (!/^[0-9,]*$/.test(raw)) {
          input.setCustomValidity('숫자만 입력해 주세요.');
          return;
        }
        const before = raw.slice(0, input.selectionStart ?? raw.length).replace(/,/g, '').length;
        const digits = raw.replace(/,/g, '').replace(/^0+(?=\d)/, '');
        input.value = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        let cursor = 0;
        let count = 0;
        const removedZeros = raw.replace(/,/g, '').length - digits.length;
        const target = Math.max(0, before - removedZeros);
        while (cursor < input.value.length && count < target) {
          if (input.value[cursor] !== ',') count++;
          cursor++;
        }
        input.setSelectionRange(cursor, cursor);
        const amount = digits ? BigInt(digits) : 0n;
        input.setCustomValidity(digits && (amount < 1n || amount > 1000000000000n)
          ? '1 이상 1,000,000,000,000 이하로 입력해 주세요.' : '');
      }
      input.addEventListener('input', formatInput);
      inputLabel.append(input);
      row.append(inputLabel, make('span', action === 'convert' ? 'P' : '원', 'wallet-input-unit'));
      form.append(row);
      const presets = make('div', '', 'wallet-presets');
      const suggested = action === 'convert' ? [100, 500, 1000, 5000, 10000] : [30000, 50000, 100000, 500000, 1000000];
      for (const amount of suggested) {
        const button = make('button', format(amount), 'wallet-preset');
        button.type = 'button';
        button.onclick = () => { input.value = format(amount); input.dispatchEvent(new Event('input')); input.focus(); };
        presets.append(button);
      }
      form.append(presets);
      if (action === 'deposit') {
        const fallback = {id: '', name: '보너스를 선택하지 않음', description: '', bonusPercent: '0', bonusBasisPoints: 0, destination: 'balance', rolling: Object.fromEntries(data.rollingCategories.map(item => [item.key, 100]))};
        const options = data.bonuses.some(option => option.bonusBasisPoints === 0) ? data.bonuses : [...data.bonuses, fallback];
        let selected = options.find(option => option.bonusBasisPoints === 0) || fallback;
        const choices = make('fieldset', '', 'wallet-bonus-choices');
        choices.append(make('legend', '입금 보너스 선택'));
        const labels = [];
        for (const option of options) {
          const choice = make('label', '', 'wallet-bonus-choice');
          const radio = document.createElement('input');
          radio.type = 'radio';
          radio.name = 'bonus_id';
          radio.value = String(option.id);
          radio.checked = option.id === selected.id;
          const mark = make('span', '✓', 'wallet-bonus-mark');
          mark.setAttribute('aria-hidden', 'true');
          const text = make('span', '', 'wallet-bonus-copy');
          text.append(make('strong', option.name));
          if (option.description) text.append(make('small', option.description));
          choice.append(radio, mark, text);
          choice.classList.toggle('selected', radio.checked);
          radio.onchange = () => {
            selected = option;
            labels.forEach(item => item.label.classList.toggle('selected', item.radio.checked));
            updateBonus();
          };
          labels.push({label: choice, radio});
          choices.append(choice);
        }
        form.append(choices);
        const bonusSection = make('section', '', 'wallet-conditions');
        bonusSection.append(make('h3', '입금보너스 안내'));
        const bonusSummary = make('dl', '', 'wallet-condition-table');
        bonusSection.append(bonusSummary);
        const rollingSection = make('section', '', 'wallet-conditions');
        rollingSection.append(make('h3', '롤링퍼센트 안내'));
        const rollingSummary = make('dl', '', 'wallet-condition-table');
        rollingSection.append(rollingSummary);
        form.append(bonusSection, rollingSection);
        function conditionRow(target, label, value, className = '') {
          const row = make('div', '', 'wallet-condition-row');
          row.append(make('dt', label), make('dd', value, className));
          target.append(row);
        }
        function updateBonus() {
          const digits = input.value.replace(/,/g, '');
          const amount = /^\d+$/.test(digits) ? BigInt(digits) : 0n;
          const bonus = amount * BigInt(selected.bonusBasisPoints) / 10000n;
          bonusSummary.replaceChildren();
          conditionRow(bonusSummary, '입금보너스', Number(selected.bonusPercent) + '%');
          conditionRow(bonusSummary, '보너스 지급액', format(bonus) + (selected.destination === 'points' ? 'P' : '원'), 'wallet-condition-highlight');
          conditionRow(bonusSummary, '보너스 이름', selected.name);
          conditionRow(bonusSummary, '지급 대상', selected.destination === 'points' ? '보유 포인트' : '보유금액');
          rollingSummary.replaceChildren();
          for (const category of data.rollingCategories) {
            const percent = selected.rolling[category.key];
            conditionRow(rollingSummary, category.label, percent === null ? '이용불가' : format(percent) + '%', percent === null ? 'wallet-condition-forbidden' : 'wallet-condition-highlight');
          }
        }
        input.addEventListener('input', updateBonus);
        updateBonus();

        const accountSection = make('section', '', 'wallet-conditions wallet-account-section');
        accountSection.append(make('h3', '입금 계좌 확인'));
        const accountButton = make('button', '입금 계좌 요청', 'secondary-button wallet-account-button');
        accountButton.type = 'button';
        const accountDetails = make('div', '', 'wallet-account-details');
        accountDetails.setAttribute('aria-live', 'polite');
        let pendingAccount = false;
        let accountRequestVersion = 0;
        function showAccountReply(payload) {
          accountDetails.replaceChildren();
          pendingAccount = payload.request?.status === 'pending';
          if (pendingAccount) {
            accountDetails.textContent = '입금 계좌 요청이 관리자에게 접수되었습니다. 안내 확인 버튼으로 답변을 확인해 주세요.';
            accountButton.textContent = '계좌 안내 확인';
            return;
          }
          accountButton.textContent = payload.account ? '계좌 다시 요청' : '입금 계좌 요청';
          if (!payload.account) return;
          const details = make('dl', '', 'wallet-condition-table');
          conditionRow(details, '은행명', payload.account.bankName);
          conditionRow(details, '계좌번호', payload.account.accountNumber);
          conditionRow(details, '예금주', payload.account.accountHolder);
          accountDetails.append(details);
          if (payload.account.instructions) accountDetails.append(make('p', payload.account.instructions, 'wallet-account-instructions'));
        }
        accountButton.onclick = async () => {
          const requestVersion = ++accountRequestVersion;
          accountButton.disabled = true;
          accountDetails.textContent = '입금 계좌를 확인하고 있습니다.';
          try {
            const sessionResponse = await fetch('/api/accounts/session/', {cache: 'no-store', credentials: 'same-origin'});
            if (!sessionResponse.ok) throw new Error('session failed');
            const session = await sessionResponse.json();
            const response = await fetch('/api/wallet/account-request/', {
              method: pendingAccount ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', headers: {'X-CSRFToken': session.csrfToken}
            });
            const payload = await response.json();
            if (!form.isConnected || requestVersion !== accountRequestVersion) return;
            if (response.status === 401) { loginPrompt(); return; }
            if (!response.ok) {
              accountDetails.textContent = payload.message || '계좌를 확인하지 못했습니다.';
              return;
            }
            showAccountReply(payload);
          } catch {
            accountDetails.textContent = '연결 오류입니다. 다시 시도해 주세요.';
          } finally {
            accountButton.disabled = false;
          }
        };
        accountSection.append(accountButton, accountDetails);
        form.append(accountSection);
        fetch('/api/wallet/account-request/', {cache: 'no-store', credentials: 'same-origin'})
          .then(response => response.ok ? response.json() : null)
          .then(payload => { if (payload && form.isConnected && accountRequestVersion === 0) showAccountReply(payload); })
          .catch(() => {});
      }
      const help = {
        deposit: '신청 후 관리자 승인 전까지 보유금액은 변하지 않습니다.',
        withdraw: '신청 금액은 즉시 사용 가능한 보유금액에서 분리됩니다. 거절되면 반환됩니다.',
        convert: '1P = 1원입니다. 전환하면 보유 포인트가 줄고 보유금액이 늘어납니다.'
      };
      form.append(make('p', help[action], 'wallet-form-help'));
      const feedback = make('p', '', 'wallet-feedback');
      feedback.setAttribute('role', 'alert');
      feedback.hidden = true;
      const submit = make('button', label, 'primary-button wallet-submit');
      submit.type = 'submit';
      form.append(feedback, submit);
      form.onsubmit = async event => {
        event.preventDefault();
        submit.disabled = true;
        feedback.hidden = true;
        try {
          const sessionResponse = await fetch('/api/accounts/session/', {cache: 'no-store', credentials: 'same-origin'});
          if (!sessionResponse.ok) throw new Error('session failed');
          const session = await sessionResponse.json();
          const body = new URLSearchParams(new FormData(form));
          body.set(input.name, input.value.replace(/,/g, ''));
          if (action !== 'convert') body.set('kind', action);
          const result = await fetch('/api/wallet/' + (action === 'convert' ? 'convert/' : 'apply/'), {
            method: 'POST', credentials: 'same-origin',
            headers: {'X-CSRFToken': session.csrfToken}, body
          });
          const payload = await result.json();
          if (!panel.isConnected) return;
          if (result.status === 401) { loginPrompt(); return; }
          if (!result.ok) {
            feedback.textContent = payload.message || '처리하지 못했습니다.';
            feedback.hidden = false;
            return;
          }
          await renderWallet();
          const message = action === 'convert' ? '포인트가 보유금액으로 전환되었습니다.' : label + '이 접수되었습니다.';
          document.querySelector('#wallet-content')?.prepend(make('p', message, 'wallet-success'));
        } catch {
          feedback.textContent = '연결 오류입니다. 다시 시도해 주세요.';
          feedback.hidden = false;
        } finally {
          submit.disabled = false;
        }
      };
      formArea.append(form);
    }
    showForm();

    const history = make('section', '', 'wallet-panel');
    history.append(make('h2', '입출금 신청 내역', 'wallet-panel-title'));
    const tableWrap = make('div', '', 'wallet-table-wrap');
    const table = make('table', '', 'wallet-table');
    const head = document.createElement('thead');
    const headerRow = document.createElement('tr');
    for (const heading of ['번호', '시간', '신청 유형', '신청 금액', '상태']) headerRow.append(make('th', heading));
    head.append(headerRow);
    const body = document.createElement('tbody');
    const kindLabels = {deposit: '입금', withdraw: '출금'};
    const statusLabels = {pending: '승인 대기', approved: '승인 완료', rejected: '거절'};
    for (const item of data.requests) {
      const row = document.createElement('tr');
      row.append(make('td', String(item.id)));
      row.append(make('td', dateTime(item.createdAt)));
      row.append(make('td', kindLabels[item.kind] || item.kind));
      const amountCell = make('td', format(item.amount) + '원');
      if (item.kind === 'deposit' && item.bonusName) {
        amountCell.append(make('small', item.bonusName + ' · +' + format(item.bonusAmount) + (item.bonusDestination === 'points' ? 'P' : '원'), 'wallet-history-bonus'));
      }
      row.append(amountCell);
      const statusCell = document.createElement('td');
      statusCell.append(make('span', statusLabels[item.status] || item.status, 'wallet-status wallet-status-' + item.status));
      row.append(statusCell);
      body.append(row);
    }
    if (!data.requests.length) {
      const row = document.createElement('tr');
      const empty = make('td', '신청 내역이 없습니다.', 'wallet-table-empty');
      empty.colSpan = 5;
      row.append(empty);
      body.append(row);
    }
    table.append(head, body);
    tableWrap.append(table);
    history.append(tableWrap);
    history.append(make('p', '표를 좌우로 밀어 전체 내역을 확인할 수 있습니다.', 'wallet-table-hint'));
    const pagination = make('div', '', 'wallet-pagination');
    const pageInfo = make('span', data.page + ' / ' + data.pages + ' 페이지');
    const pageLinks = make('div');
    for (const [number, label] of [[data.page - 1, '‹ 이전'], [data.page + 1, '다음 ›']]) {
      const button = make('a', label, 'secondary-button');
      if (number < 1 || number > data.pages) {
        button.setAttribute('aria-disabled', 'true');
        button.classList.add('wallet-page-disabled');
      } else {
        const url = new URL(location.href);
        url.searchParams.set('walletPage', String(number));
        url.hash = '/wallet';
        button.href = url.pathname + url.search + url.hash;
      }
      pageLinks.append(button);
    }
    pagination.append(pageInfo, pageLinks);
    history.append(pagination);
    right.append(history);

    const pointHistory = make('section', '', 'wallet-panel');
    pointHistory.append(make('h2', '최근 포인트 내역', 'wallet-panel-title'));
    const pointList = make('div', '', 'wallet-point-list');
    if (!data.grants.length && !data.conversions.length) pointList.append(make('p', '포인트 내역이 없습니다.', 'wallet-empty'));
    const pointEvents = [
      ...data.grants.map(grant => ({type: 'grant', ...grant})),
      ...data.conversions.map(conversion => ({type: 'conversion', ...conversion}))
    ].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    for (const event of pointEvents) {
      const row = make('div', '', 'wallet-point-row');
      const label = event.type === 'grant' ? '지급 · ' + event.reason : '보유금액 전환';
      const sign = event.type === 'grant' ? '+' : '-';
      row.append(make('span', label + ' · ' + dateTime(event.createdAt)), make('strong', sign + format(event.points) + 'P'));
      pointList.append(row);
    }
    pointHistory.append(pointList);
    right.append(pointHistory);
  } catch {
    if (panel.isConnected) panel.textContent = '금액 정보를 불러오지 못했습니다. 새로고침하여 다시 시도해 주세요.';
  }
}

window.addEventListener('account-changed', () => {
  if (location.hash === '#/wallet') renderWallet();
});
