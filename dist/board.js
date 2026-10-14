async function renderBoard(id) {
  const view=document.querySelector('.route-view');
  view.innerHTML=pageHeading('게시판','회원이 함께 나누는 이야기와 공지사항')+'<div id="board-content" class="detail-panel" aria-live="polite">불러오는 중…</div>';
  const panel=view.querySelector('#board-content');
  const text=(tag,value,cls)=>{const node=document.createElement(tag);node.textContent=value;if(cls)node.className=cls;return node;};
  const date=value=>new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',dateStyle:'medium'}).format(new Date(value));
  try {
    if(id==='new'){
      const session=await(await fetch('/api/accounts/session/',{cache:'no-store'})).json();if(!panel.isConnected)return;
      if(!session.authenticated){panel.innerHTML='<p>로그인 후 글을 작성해 주세요.</p><button class="secondary-button" type="button">로그인</button>';panel.querySelector('button').onclick=()=>openDialog('login');return;}
      panel.innerHTML='<form id="board-form"><div class="auth-feedback" role="alert" hidden></div><label>제목<input name="title" maxlength="200" required></label><label>내용<textarea name="body" maxlength="10000" rows="8" required></textarea></label><div class="detail-actions"><button type="submit" class="secondary-button">글 등록</button><a class="secondary-button" href="#/board">취소</a></div></form>';
      const form=panel.querySelector('form');form.onsubmit=async event=>{
        event.preventDefault();const button=form.querySelector('button');const feedback=form.querySelector('.auth-feedback');button.disabled=true;feedback.hidden=true;
        try{const session=await(await fetch('/api/accounts/session/',{cache:'no-store'})).json();const response=await fetch('/api/board/',{method:'POST',headers:{'X-CSRFToken':session.csrfToken},body:new URLSearchParams(new FormData(form))});const result=await response.json();if(!panel.isConnected)return;
          if(!response.ok){feedback.textContent=Object.values(result.errors||{}).flat().map(e=>e.message).join(' ')||result.message||'글 등록에 실패했습니다.';feedback.hidden=false;return;}location.hash='#/board/'+result.post.id;
        }catch{feedback.textContent='글 등록에 실패했습니다. 다시 시도해 주세요.';feedback.hidden=false;}finally{button.disabled=false;}
      };return;
    }
    if(id!==undefined&&!/^[1-9][0-9]*$/.test(id)){panel.textContent='게시글을 찾을 수 없습니다.';return;}
    const params=new URLSearchParams(location.search);
    const page=params.get('boardPage')||'1';
    const query=(params.get('boardSearch')||'').trim().slice(0,200);
    const response=await fetch('/api/board/'+(id===undefined?'?page='+encodeURIComponent(page)+'&q='+encodeURIComponent(query):id+'/'),{cache:'no-store'});if(!panel.isConnected)return;
    if(response.status===404){panel.textContent='게시글을 찾을 수 없습니다.';return;}if(!response.ok)throw new Error();const result=await response.json();if(!panel.isConnected)return;panel.replaceChildren();
    if(id===undefined){
      const search=document.createElement('form');search.id='board-search-form';search.className='route-tools';
      search.innerHTML='<label>게시글 검색<input name="q" type="search" maxlength="200" placeholder="제목 또는 내용 검색"></label><button type="submit" class="secondary-button">검색</button><button type="button" class="secondary-button" id="board-search-clear">전체 보기</button>';
      search.querySelector('input').value=result.query;
      function searchUrl(value){const url=new URL(location.href);url.searchParams.delete('boardPage');url.searchParams.delete('boardSearch');if(value)url.searchParams.set('boardSearch',value);url.hash='/board';return url.pathname+url.search+url.hash;}
      search.onsubmit=event=>{event.preventDefault();location.href=searchUrl(search.querySelector('input').value.trim());};
      search.querySelector('#board-search-clear').onclick=()=>location.href=searchUrl('');
      panel.append(search,text('p',(result.query?'검색 결과 ':'전체 게시글 ')+result.count+'개','muted'));
      const create=text('a','글쓰기','secondary-button');create.href='#/board/new';panel.append(create);
      for(const notice of result.pinnedNotices){const link=text('a','[공지사항] '+notice.title,'notice-row board-pinned');link.href='#/notices/'+notice.id;panel.append(link);}
      if(!result.items.length)panel.append(text('p',result.query?'검색 결과가 없습니다.':'등록된 게시글이 없습니다.'));
      for(const post of result.items){const link=text('a','','notice-row');link.href='#/board/'+post.id;link.append(text('strong',post.id + '. ' + post.title),text('span',post.author+' · '+date(post.createdAt),'muted'));panel.append(link);}
      const pagination=text('div','','detail-actions');for(const [number,label] of [[result.page-1,'이전'],[result.page+1,'다음']]){if(number<1||number>result.pages)continue;const link=text('a',label,'secondary-button');const url=new URL(location.href);url.searchParams.set('boardPage',number);url.hash='/board';link.href=url.pathname+url.search+url.hash;pagination.append(link);}panel.append(pagination);
    }else{const post=result.post;panel.append(text('h2',post.id + '. ' + post.title),text('p',post.author+' · '+date(post.createdAt),'muted'),text('div',post.body,'notice-body'));const back=text('a','목록으로','secondary-button');back.href='#/board';panel.append(back);}
  }catch{if(panel.isConnected)panel.textContent='게시판을 불러오지 못했습니다. 새로고침하여 다시 시도해 주세요.';}
}
window.addEventListener('account-changed',()=>{if(location.hash==='#/board/new')renderBoard('new');});
