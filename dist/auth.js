// Session cookies stay in the browser; credentials are never stored in browser storage.
const accountControls = document.querySelector('.header-sub > div');
const authForms = [...document.querySelectorAll('#login form, #signup form, #password-change form, #profile form')];
const fieldNames = {old_password: '현재 비밀번호', new_password1: '새 비밀번호', new_password2: '새 비밀번호 확인', username: '아이디', nickname: '닉네임', password: '비밀번호', password1: '비밀번호', password2: '비밀번호 확인'};
const notice = document.createElement('div');
notice.className = 'auth-notice';
notice.setAttribute('role', 'status');
notice.hidden = true;
document.body.append(notice);
let noticeTimer;
function notifyAuth(message) {
  clearTimeout(noticeTimer);
  notice.textContent = message;
  notice.hidden = false;
  noticeTimer = setTimeout(() => notice.hidden = true, 6000);
}
function showAuthErrors(form, messages) {
  const feedback = form.querySelector('.auth-feedback');
  feedback.replaceChildren();
  messages.forEach(message => {const line = document.createElement('p'); line.textContent = message; feedback.append(line);});
  feedback.hidden = messages.length === 0;
}
authForms.forEach(form => {
  const feedback = document.createElement('div');
  feedback.className = 'auth-feedback';
  feedback.setAttribute('role', 'alert');
  feedback.hidden = true;
  form.prepend(feedback);
  form.closest('dialog').addEventListener('close', () => {showAuthErrors(form, []); form.reset();});
});
async function readAuthResponse(response) {
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('회원 서버에 연결할 수 없습니다. 개발 서버가 실행 중인지 확인해 주세요.');
  }
  return response.json();
}
async function getSession() {
  const response = await fetch('/api/accounts/session/', {cache: 'no-store', credentials: 'same-origin', mode: 'same-origin'});
  const data = await readAuthResponse(response);
  if (!response.ok || !data.ok) throw new Error('로그인 상태를 확인하지 못했습니다. 다시 시도해 주세요.');
  return data;
}
function renderAccount(data) {
  accountControls.replaceChildren();
  window.dispatchEvent(new Event('account-changed'));
  if (data.authenticated) {
    const name = document.createElement('a');
    name.href = '#/account';
    name.setAttribute('aria-label', '내 계정');
    name.title = '내 계정 보기';
    name.className = 'account-name';
    name.textContent = (data.user.nickname || data.user.username) + '님';
    const logoutButton = document.createElement('button');
    logoutButton.className = 'text-button gold';
    logoutButton.id = 'logout-button';
    logoutButton.textContent = '로그아웃';
    logoutButton.addEventListener('click', async () => {
      logoutButton.disabled = true;
      try {
        const current = await getSession();
        const response = await fetch('/api/accounts/logout/', {method: 'POST', credentials: 'same-origin', mode: 'same-origin', headers: {'X-CSRFToken': current.csrfToken}});
        const result = await readAuthResponse(response);
        if (!response.ok || !result.ok) throw new Error(result.message || '로그아웃하지 못했습니다. 다시 시도해 주세요.');
        renderAccount(result);
        notifyAuth('로그아웃되었습니다.');
      } catch (error) {notifyAuth(error.message || '연결 오류입니다. 다시 시도해 주세요.');}
      finally {logoutButton.disabled = false;}
    });
    const passwordButton = document.createElement('button');
    passwordButton.className = 'text-button';
    passwordButton.id = 'password-change-button';
    passwordButton.textContent = '비밀번호 변경';
    passwordButton.addEventListener('click', () => openDialog('password-change'));
    const profileButton = document.createElement('button');
    profileButton.className = 'text-button';
    profileButton.id = 'profile-button';
    profileButton.textContent = '회원정보 수정';
    profileButton.addEventListener('click', async () => {
      profileButton.disabled = true;
      try {
        const current = await getSession();
        renderAccount(current);
        if (!current.authenticated) {notifyAuth('로그인 후 회원정보를 수정해 주세요.'); return;}
        openDialog('profile');
        document.querySelector('#profile [name="nickname"]').value = current.user.nickname;
      } catch (error) {notifyAuth(error.message);}
      finally {profileButton.disabled = false;}
    });
    accountControls.append(name, profileButton, passwordButton, logoutButton);
  } else {
    for (const [id, label] of [['login', 'Login'], ['signup', 'Sign up']]) {
      const button = document.createElement('button');
      button.className = 'text-button' + (id === 'login' ? ' gold' : '');
      button.dataset.open = id;
      button.textContent = label;
      button.addEventListener('click', () => openDialog(id));
      if (id === 'signup') {const separator = document.createElement('span'); separator.className = 'muted'; separator.textContent = ' or '; accountControls.append(separator);}
      accountControls.append(button);
    }
  }
}
authForms.forEach(form => form.addEventListener('submit', async event => {
  event.preventDefault();
  showAuthErrors(form, []);
  if (!['http:', 'https:'].includes(location.protocol)) {
    showAuthErrors(form, ['회원가입·로그인은 http://127.0.0.1:8000/에서 이용해 주세요. 파일을 직접 연 화면에서는 서버에 연결하지 않습니다.']);
    return;
  }
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  const caption = submit.textContent;
  submit.textContent = '처리 중…';
  try {
    const current = await getSession();
    const action = form.closest('dialog').id;
    const response = await fetch('/api/accounts/' + action + '/', {
      method: 'POST', credentials: 'same-origin', mode: 'same-origin',
      headers: {'X-CSRFToken': current.csrfToken}, body: new URLSearchParams(new FormData(form))
    });
    const result = await readAuthResponse(response);
    if (!response.ok || !result.ok) {
      const messages = [];
      for (const [field, errors] of Object.entries(result.errors || {})) {
        errors.forEach(error => messages.push((fieldNames[field] ? fieldNames[field] + ': ' : '') + error.message));
      }
      showAuthErrors(form, messages.length ? messages : [result.message || '요청을 처리하지 못했습니다. 다시 시도해 주세요.']);
      return;
    }
    renderAccount(result);
    form.reset();
    form.closest('dialog').close();
    notifyAuth(result.message || (action === 'signup' ? '가입 신청이 완료되었습니다. 관리자 승인 후 로그인해 주세요.' : '로그인되었습니다.'));
  } catch (error) {
    showAuthErrors(form, [error.message || '연결 오류입니다. 잠시 후 다시 시도해 주세요.']);
  } finally {submit.disabled = false; submit.textContent = caption;}
}));
if (['http:', 'https:'].includes(location.protocol)) {
  getSession().then(renderAccount).catch(() => notifyAuth('회원 서버 연결을 확인해 주세요. 로그인 상태를 가져오지 못했습니다.'));
}
