let inquiryRequest = 0;
async function renderInquiries(id) {
  const requestId = ++inquiryRequest;
  const routePanel = document.querySelector('.route-view');
  routePanel.innerHTML = pageHeading('1:1 문의', '내 문의와 관리자 답변을 확인하세요.') + '<div id="inquiry-content" class="detail-panel" aria-live="polite">불러오는 중…</div>';
  const panel = routePanel.querySelector('#inquiry-content');
  const valid = () => requestId === inquiryRequest && panel.isConnected;
  const text = (tag, content, className) => {const node = document.createElement(tag);node.textContent = content;if(className)node.className=className;return node;};
  const date = value => new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',dateStyle:'medium',timeStyle:'short'}).format(new Date(value));
  function loginPrompt() {
    panel.replaceChildren(text('p','로그인 후 1:1 문의를 이용해 주세요.'));
    const button=text('button','로그인','secondary-button');button.type='button';button.addEventListener('click',()=>openDialog('login'));panel.append(button);
  }
  try {
    const sessionResponse = await fetch('/api/accounts/session/',{cache:'no-store',mode:'same-origin'});
    if(!sessionResponse.ok)throw new Error();
    const session = await sessionResponse.json();if(!valid())return;
    if(!session.authenticated){loginPrompt();return;}
    if(id === 'new') {
      panel.innerHTML = '<form id="inquiry-form"><div class="auth-feedback" role="alert" hidden></div><label>제목<input name="title" maxlength="200" required></label><label>문의 내용<textarea name="body" maxlength="10000" rows="8" required></textarea></label><div class="detail-actions"><button class="secondary-button" type="submit">문의 등록</button><a class="secondary-button" href="#/inquiries">취소</a></div></form>';
      const form=panel.querySelector('form');
      form.addEventListener('submit',async event=>{
        event.preventDefault();const submit=form.querySelector('[type="submit"]');const feedback=form.querySelector('.auth-feedback');submit.disabled=true;feedback.hidden=true;
        try{
          const fresh=await fetch('/api/accounts/session/',{cache:'no-store',mode:'same-origin'});const current=await fresh.json();
          const response=await fetch('/api/inquiries/',{method:'POST',mode:'same-origin',headers:{'X-CSRFToken':current.csrfToken},body:new URLSearchParams(new FormData(form))});
          const result=await response.json();if(!valid())return;
          if(response.status===401){loginPrompt();return;}
          if(!response.ok){const errors=Object.values(result.errors||{}).flat().map(error=>error.message);feedback.textContent=errors.join(' ')||result.message||'문의 등록에 실패했습니다.';feedback.hidden=false;return;}
          location.hash='#/inquiries/'+result.inquiry.id;
        }catch{if(valid()){feedback.textContent='문의 등록에 실패했습니다. 다시 시도해 주세요.';feedback.hidden=false;}}
        finally{submit.disabled=false;}
      });return;
    }
    if(id!==undefined&&!/^[1-9][0-9]*$/.test(id)){panel.textContent='문의를 찾을 수 없습니다.';return;}
    const page=new URLSearchParams(location.search).get('inquiryPage')||'1';
    const response=await fetch('/api/inquiries/'+(id===undefined?'?page='+encodeURIComponent(page):id+'/'),{cache:'no-store',mode:'same-origin'});
    if(!valid())return;
    if(response.status===401){loginPrompt();return;}
    if(response.status===404){panel.textContent='문의를 찾을 수 없습니다.';return;}
    if(!response.ok)throw new Error();const result=await response.json();if(!valid())return;panel.replaceChildren();
    if(id===undefined){
      const add=text('a','문의 작성','secondary-button');add.href='#/inquiries/new';panel.append(add);
      if(!result.items.length)panel.append(text('p','등록한 문의가 없습니다.'));
      for(const item of result.items){const link=text('a','','notice-row');link.href='#/inquiries/'+item.id;link.append(text('strong',item.title),text('span',(item.unread?'새 답변':item.answered?'답변 완료':'답변 대기')+' · '+date(item.createdAt),'muted'));panel.append(link);}
      const pagination=text('div','','detail-actions');for(const [number,label] of [[result.page-1,'이전'],[result.page+1,'다음']]){if(number<1||number>result.pages)continue;const link=text('a',label,'secondary-button');link.href='?inquiryPage='+number+'#/inquiries';pagination.append(link);}panel.append(pagination);
    }else{
      const item=result.inquiry;panel.append(text('h2',item.title),text('p','문의일 '+date(item.createdAt),'muted'),text('div',item.body,'notice-body'),text('h3',item.answered?'관리자 답변':'답변 대기'),text('div',item.answer||'관리자가 확인 후 답변드립니다.','notice-body'));
      if (item.answered && item.unread) {
        const read = await fetch('/api/inquiries/' + item.id + '/read/', {method:'POST',mode:'same-origin',headers:{'X-CSRFToken':session.csrfToken},body:new URLSearchParams({answered_at:item.answeredAt || ''})});
        if (read.ok) window.dispatchEvent(new Event('inquiry-read'));
      }
      if(item.answeredAt)panel.append(text('p','답변일 '+date(item.answeredAt),'muted'));const back=text('a','목록으로','secondary-button');back.href='#/inquiries';panel.append(back);
    }
  }catch{if(valid())panel.textContent='문의를 불러오지 못했습니다. 새로고침하여 다시 시도해 주세요.';}
}
window.addEventListener('account-changed',()=>{const parts=location.hash.replace(/^#\/?/,'').split('/');if(parts[0]==='inquiries')renderInquiries(parts[1]);});
