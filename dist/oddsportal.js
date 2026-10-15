let stopOddsPortal=null;
async function renderOddsPortal() {
  routeView.innerHTML=pageHeading('OddsPortal 경기·결과','종료된 경기는 경기 목록에서 자동으로 제외됩니다.')+'<div class="detail-actions"><button class="secondary-button" id="op-active">경기 목록</button><button class="secondary-button" id="op-results">종료 경기 결과</button></div><div class="detail-panel" id="op-data">불러오는 중…</div>';
  const panel=routeView.querySelector('#op-data');let scope='active',generation=0,stopped=false,currentRequest=null;
  const filters=document.createElement('div');filters.className='route-tools';
  const sportSelect=document.createElement('select'),leagueSelect=document.createElement('select');
  sportSelect.setAttribute('aria-label','종목');leagueSelect.setAttribute('aria-label','리그');filters.append(sportSelect,leagueSelect);panel.before(filters);
  const fill=(select,entries,label)=>{const value=select.value;select.replaceChildren(new Option(label,''));for(const [key,name] of entries)select.add(new Option(name,key));select.value=[...select.options].some(option=>option.value===value)?value:'';};
  async function refresh(){
    if(stopped||document.hidden||!panel.isConnected)return;
    const version=++generation;
    currentRequest?.abort();currentRequest=new AbortController();
    try{
      const response=await fetch('/api/sports/oddsportal/?scope='+scope,{cache:'no-store',signal:currentRequest.signal});const data=await response.json();
      if(stopped||version!==generation||!panel.isConnected)return;if(!response.ok)throw Error(data.message);
      fill(sportSelect,[...new Map(data.items.map(item=>[item.sportKey||'other',item.sportLabel||'기타'])).entries()].sort((a,b)=>a[1].localeCompare(b[1])),'전체 종목');
      const sportItems=data.items.filter(item=>!sportSelect.value||item.sportKey===sportSelect.value);
      fill(leagueSelect,[...new Map(sportItems.map(item=>[item.leagueKey||item.league||'unknown',item.league||'리그 미확인'])).entries()].sort((a,b)=>a[1].localeCompare(b[1])),'전체 리그');
      data.items=sportItems.filter(item=>!leagueSelect.value||(item.leagueKey||item.league||'unknown')===leagueSelect.value);
      panel.innerHTML='<p id="op-time" role="status"></p><p id="op-error" role="alert"></p><p>화면은 30초마다 갱신됩니다. 종료 상태는 서버가 원본 사이트에서 결과를 수신한 후 반영됩니다.</p><div style="overflow:auto"><table style="width:100%;min-width:700px"><thead><tr><th>경기</th><th>상태</th><th>점수</th><th>배당</th></tr></thead><tbody></tbody></table></div>';
      panel.querySelector('#op-time').textContent='최근 수집: '+new Date(data.fetchedAt).toLocaleString('ko-KR')+' · 진행·예정 '+data.activeCount+'경기 · 종료 '+data.resultCount+'경기';
      panel.querySelector('#op-error').textContent=data.error?'수집 오류: '+data.error:'';
      const body=panel.querySelector('tbody');
      const table=panel.querySelector('table');table.className='op-line-table';table.querySelector('thead tr').replaceChildren();
      for(const label of ['시간','리그','홈팀','배당','무승부 / 기준','배당','원정팀','점수']){const th=document.createElement('th');th.textContent=label;table.querySelector('thead tr').append(th);}
      for(const item of data.items){const tr=document.createElement('tr');tr.dataset.eventId=item.id;const odds=(item.odds||[]).map(value=>value!==null&&value!==''&&Number.isFinite(Number(value))?Number(value).toFixed(2):'?');const start=Date.parse(item.startsAt);const time=Number.isFinite(start)?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(start):item.statusText||'—';
      const values=[time,item.league||item.sport||'—',item.home,odds[0]||'—',odds.length===3?odds[1]:'VS',odds.length>1?odds[odds.length-1]||'—':'—',item.away,item.scores?item.scores.join(' : '):'—'];
      values.forEach((value,index)=>{const td=document.createElement('td');td.textContent=value;if([2,3,5,6].includes(index))td.className='op-team-cell';if(item.status==='finished'&&Array.isArray(item.scores)&&item.scores.length===2&&item.scores.every(v=>v!==null&&Number.isFinite(Number(v)))){const winner=Number(item.scores[0])>Number(item.scores[1])?2:Number(item.scores[1])>Number(item.scores[0])?6:-1;if(index===winner){td.classList.add('winner');td.setAttribute('aria-label','\uC2B9\uB9AC\uD300');}}tr.append(td);});body.append(tr);}
      if(!data.items.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=8;td.textContent=scope==='active'?'진행·예정 경기가 없습니다.':'종료된 경기가 없습니다.';tr.append(td);body.append(tr);}
      routeView.querySelector('#op-active').textContent='경기 목록 ('+data.activeCount+')';routeView.querySelector('#op-results').textContent='종료 경기 결과 ('+data.resultCount+')';
      routeView.querySelector('#op-active').setAttribute('aria-pressed',String(scope==='active'));routeView.querySelector('#op-results').setAttribute('aria-pressed',String(scope==='results'));
    }catch(e){if(e.name==='AbortError'||stopped||version!==generation||!panel.isConnected)return;let error=panel.querySelector('#op-error');if(!error){error=document.createElement('p');error.id='op-error';error.setAttribute('role','alert');panel.prepend(error);}error.textContent=e.message||'목록을 갱신하지 못했습니다.';}
  }
  routeView.querySelector('#op-active').onclick=()=>{scope='active';refresh();};
  sportSelect.onchange=()=>{leagueSelect.value='';refresh();};leagueSelect.onchange=refresh;
  routeView.querySelector('#op-results').onclick=()=>{scope='results';refresh();};
  const timer=setInterval(refresh,30000);document.addEventListener('visibilitychange',refresh);
  stopOddsPortal=()=>{stopped=true;generation++;clearInterval(timer);document.removeEventListener('visibilitychange',refresh);currentRequest?.abort();};
  await refresh();
}
