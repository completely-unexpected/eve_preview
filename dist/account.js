let accountPageRequest = 0;

async function renderAccountPage() {
  const requestId = ++accountPageRequest;
  const view = document.querySelector('.route-view');
  view.innerHTML = pageHeading('회원정보', '회원정보와 비밀번호, 이용한도를 확인하세요.') +
    '<div id="account-page" aria-live="polite">불러오는 중…</div>';
  const panel = view.querySelector('#account-page');
  const valid = () => requestId === accountPageRequest && panel.isConnected;
  const make = (tag, text = '', className = '') => {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const format = value => new Intl.NumberFormat('ko-KR').format(value);
  const row = (target, label, value, className = '') => {
    const element = make('div', '', 'wallet-condition-row');
    element.append(make('dt', label), make('dd', value, className));
    target.append(element);
  };
  try {
    const response = await fetch('/api/accounts/details/', {cache: 'no-store', credentials: 'same-origin'});
    if (!valid()) return;
    if (response.status === 401) {
      panel.replaceChildren(make('p', '로그인 후 회원정보를 확인해 주세요.'));
      const button = make('button', '로그인', 'primary-button');
      button.type = 'button';
      button.onclick = () => openDialog('login');
      panel.append(button);
      return;
    }
    if (!response.ok) throw new Error('account load failed');
    const data = await response.json();
    if (!valid()) return;
    panel.replaceChildren();
    const layout = make('div', '', 'wallet-layout member-layout');
    const left = make('div', '', 'wallet-column');
    const right = make('div', '', 'wallet-column');
    layout.append(left, right);
    panel.append(layout);

    const info = make('section', '', 'wallet-panel');
    info.append(make('h2', '회원정보', 'wallet-panel-title'));
    const details = make('dl', '', 'wallet-condition-table');
    row(details, '아이디', data.user.username);
    row(details, '레벨', data.user.level + ' · ' + data.user.levelName);
    row(details, '가입 상태', data.user.status);
    row(details, '가입일', new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', dateStyle: 'medium'}).format(new Date(data.user.joinedAt)));
    info.append(details);
    const profile = make('form', '', 'member-form');
    profile.id = 'member-profile-form';
    const nicknameLabel = make('label', '닉네임');
    const nickname = document.createElement('input');
    nickname.name = 'nickname';
    nickname.autocomplete = 'nickname';
    nickname.maxLength = 30;
    nickname.required = true;
    nickname.value = data.user.nickname;
    nicknameLabel.append(nickname);
    profile.append(nicknameLabel);
    left.append(info);
    info.append(profile);

    const passwordPanel = make('section', '', 'wallet-panel');
    passwordPanel.append(make('h2', '비밀번호 변경', 'wallet-panel-title'));
    const password = make('form', '', 'member-form');
    password.id = 'member-password-form';
    for (const [name, label, autocomplete] of [
      ['new_password1', '새 비밀번호', 'new-password'],
      ['new_password2', '새 비밀번호 확인', 'new-password'],
      ['old_password', '현재 비밀번호', 'current-password']
    ]) {
      const fieldLabel = make('label', label);
      const input = document.createElement('input');
      input.name = name;
      input.type = 'password';
      input.autocomplete = autocomplete;
      input.placeholder = label + '를 입력해 주세요';
      input.required = true;
      fieldLabel.append(input);
      password.append(fieldLabel);
    }
    passwordPanel.append(password);
    left.append(passwordPanel);

    function connectForm(form, endpoint, caption) {
      const feedback = make('div', '', 'auth-feedback');
      feedback.setAttribute('role', 'alert');
      feedback.hidden = true;
      const submit = make('button', caption, 'primary-button');
      submit.type = 'submit';
      form.append(feedback, submit);
      form.onsubmit = async event => {
        event.preventDefault();
        feedback.replaceChildren();
        feedback.hidden = true;
        submit.disabled = true;
        try {
          const session = await getSession();
          const response = await fetch('/api/accounts/' + endpoint + '/', {
            method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': session.csrfToken},
            body: new URLSearchParams(new FormData(form))
          });
          const result = await readAuthResponse(response);
          if (!valid()) return;
          if (!response.ok || !result.ok) {
            for (const [field, errors] of Object.entries(result.errors || {})) {
              for (const error of errors) feedback.append(make('p', (fieldNames[field] ? fieldNames[field] + ': ' : '') + error.message));
            }
            if (!feedback.childElementCount) feedback.append(make('p', result.message || '저장하지 못했습니다. 다시 시도해 주세요.'));
            feedback.hidden = false;
            return;
          }
          if (endpoint === 'password-change') form.reset();
          renderAccount(result);
          notifyAuth(result.message || '변경사항을 저장했습니다.');
        } catch (error) {
          feedback.replaceChildren(make('p', error.message || '연결 오류입니다. 다시 시도해 주세요.'));
          feedback.hidden = false;
        } finally {
          submit.disabled = false;
        }
      };
    }
    connectForm(profile, 'profile', '회원정보 저장');
    connectForm(password, 'password-change', '비밀번호 변경');

    const limits = make('section', '', 'wallet-panel');
    limits.append(make('h2', '이용한도', 'wallet-panel-title'));
    for (const [kind, label] of [['single', '싱글'], ['multi', '멀티']]) {
      limits.append(make('h3', label, 'member-limit-title'));
      const values = make('dl', '', 'wallet-condition-table');
      for (const [suffix, title] of [['min', '최소 베팅'], ['max', '최대 베팅'], ['payout', '최대 당첨']]) {
        row(values, title, format(data.limits[kind + '_' + suffix]) + '원', 'wallet-condition-highlight');
      }
      limits.append(values);
    }
    limits.append(make('p', '레벨과 이용한도는 관리자가 설정합니다.', 'member-limit-note'));
    right.append(limits);
    const shortcuts = make('div', '', 'member-shortcuts');
    for (const [href, label] of [['#/inquiries', '내 문의'], ['#/wallet', '보유금액·포인트']]) {
      const link = make('a', label, 'secondary-button');
      link.href = href;
      shortcuts.append(link);
    }
    right.append(shortcuts);
  } catch {
    if (valid()) panel.textContent = '회원정보를 불러오지 못했습니다. 새로고침해 주세요.';
  }
}

window.addEventListener('account-changed', () => {
  if (location.hash === '#/account') renderAccountPage();
});
