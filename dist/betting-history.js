let bettingHistoryGeneration=0;
function sportsHistoryRow(leg,make,time,price,marketLabel){
  const row=make('tr');
  const home=make('td',leg.home),away=make('td',leg.away);
  const homePrice=make('td','','history-price'),middle=make('td','VS','history-price'),awayPrice=make('td','','history-price');
  const selectedHome=leg.name===leg.home,selectedAway=leg.name===leg.away,draw=leg.name==='Draw';
  if(selectedHome){home.classList.add('history-selected');homePrice.textContent=price(leg.price);homePrice.classList.add('history-selected');}
  if(selectedAway){away.classList.add('history-selected');awayPrice.textContent=price(leg.price);awayPrice.classList.add('history-selected');}
  if(draw){middle.textContent=price(leg.price);middle.classList.add('history-selected');middle.setAttribute('aria-label','무승부 선택');}
  if(!draw&&leg.point!==null&&leg.point!==undefined)middle.textContent=String(leg.point);
  if(!selectedHome&&!selectedAway&&!draw){middle.textContent=(leg.name==='Over'?'오버':leg.name==='Under'?'언더':leg.name)+(leg.point!=null?' '+leg.point:'')+' · '+price(leg.price);middle.classList.add('history-selected');}
  const league=make('td',leg.league||'');if(!leg.market?.startsWith('h2h'))league.append(make('small',marketLabel,'history-market-label'));
  row.append(make('td',time(leg.startsAt)),league,home,homePrice,middle,awayPrice,away);
  const labels={pending:'정산 대기',won:'적중',lost:'미적중',void:'취소'};const result=make('td');result.append(make('span',labels[leg.result]||'대기','bet-result bet-result-'+leg.result));row.append(result);
  return row;
}
async function renderBettingHistory(){
  const view=document.querySelector('.route-view'),generation=++bettingHistoryGeneration;
  const make=(tag,text='',cls='')=>{const element=document.createElement(tag);element.textContent=text;if(cls)element.className=cls;return element;};
  const money=value=>Number(value||0).toLocaleString('ko-KR')+'원';
  const price=value=>Number(value).toFixed(2);
  const time=value=>Number.isFinite(Date.parse(value))?new Date(value).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false}):'';
  const states={pending:'정산 대기',won:'적중',lost:'미적중',void:'취소',mixed:'혼합 결과'};
  const markets={h2h:'승무패',spreads:'핸디캡',totals:'오버언더',general_parity:'일반볼 홀/짝',general_range:'일반볼 구간',power_parity:'파워볼 홀/짝',power_range:'파워볼 언더/오버'};
  view.innerHTML=pageHeading('배팅 내역','내가 접수한 경기와 처리 결과를 확인하세요.');
  const tools=make('div','','route-tools'),source=document.createElement('select');source.setAttribute('aria-label','배팅 게임 분류');
  for(const [key,label] of [['all','전체'],['sports','스포츠'],['powerball','파워볼']])source.add(new Option(label,key));
  const refresh=make('button','새로고침','secondary-button');refresh.type='button';tools.append(source,refresh);view.append(tools);
  const content=make('section','','sb-demo-history');content.setAttribute('aria-live','polite');view.append(content);let version=0,page=1;
  async function load(target=1){
    const request=++version;page=target;content.textContent='불러오는 중…';
    try{
      const response=await fetch('/api/sports/my-slips/?'+new URLSearchParams({source:source.value,page}),{cache:'no-store',credentials:'same-origin'});
      if(!content.isConnected||generation!==bettingHistoryGeneration||request!==version)return;
      const data=await response.json();if(!content.isConnected||generation!==bettingHistoryGeneration||request!==version)return;
      if(response.status===401){content.replaceChildren(make('p','로그인 후 배팅 내역을 확인할 수 있습니다.'));const login=make('button','로그인','primary-button');login.onclick=()=>document.querySelector('#login').showModal();content.append(login);return;}
      if(!response.ok||!data.ok)throw Error(data.message||'배팅 내역을 불러오지 못했습니다.');
      content.replaceChildren();
      if(!data.items.length)content.append(make('p','배팅 내역이 없습니다.','empty-state'));
      for(const item of data.items){
        const ticket=make('article','','sb-history-ticket');ticket.dataset.slipId=item.id;
        const heading=make('div','','sb-ticket-heading');heading.append(make('strong','#'+item.id+' · '+(item.source==='powerball'?'파워볼':'스포츠')+' · '+(item.mode==='multi'?'멀티':'싱글')),make('span',states[item.status]||'대기','bet-result bet-result-'+item.status),make('small',time(item.createdAt)));ticket.append(heading);
        const scroll=make('div','','sb-ticket-scroll'),table=make('table'),thead=make('thead'),header=make('tr');
        const isPowerball=item.source==='powerball';
        for(const label of isPowerball?['회차','추첨 시간','일반볼 홀/짝','일반볼 구간','파워볼 홀/짝','파워볼 언더/오버','배당','결과']:['경기 시간','리그','홈팀','배당','기준값','배당','원정팀','결과'])header.append(make('th',label));thead.append(header);table.append(thead);
        const tbody=make('tbody');
        if(isPowerball){
          const options=[['general_parity',['홀','짝']],['general_range',['대 (81~130)','중 (65~80)','소 (15~64)']],['power_parity',['홀','짝']],['power_range',['언더 (0~4)','오버 (5~9)']]];
          const groups=new Map();for(const leg of item.legs){const key=leg.eventId||leg.startsAt+'|'+leg.away;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(leg);}
          for(const legs of groups.values()){
            const tr=make('tr');tr.append(make('td',legs[0].away||legs[0].eventId),make('td',time(legs[0].startsAt)));
            for(const [key,names] of options){const td=make('td'),choices=make('div','','pb-history-options');const selected=legs.filter(leg=>leg.market===key);
              for(const name of [...new Set([...names,...selected.map(leg=>leg.name)])]){const picked=selected.filter(leg=>leg.name===name);const chip=make('span',name,'pb-history-option'+(picked.length?' selected':''));if(picked.length)chip.setAttribute('aria-label',name+' 선택');choices.append(chip);}td.append(choices);tr.append(td);}
            tr.append(make('td',legs.map(leg=>price(leg.price)).join(' / ')));const results=make('td');for(const leg of legs)results.append(make('span',(legs.length>1?(markets[leg.market]||leg.market)+' '+leg.name+' · ':'')+(states[leg.result]||'대기'),'bet-result bet-result-'+leg.result));tr.append(results);tbody.append(tr);
          }
        }else for(const leg of item.legs)tbody.append(sportsHistoryRow(leg,make,time,price,markets[leg.market]||leg.market));
        table.append(tbody);scroll.append(table);ticket.append(scroll);
        const summary=make('dl','','sb-ticket-totals');const odds=item.mode==='multi'?price(item.legs.reduce((n,leg)=>n*Number(leg.price),1)):item.legs.map(leg=>price(leg.price)).join(' / ');
        for(const [label,value] of [['배당',odds],['배팅금액',money(item.totalStake)],['적중예상금액',money(item.expectedReturn)],['적중금액',money(item.creditedAmount)]]){const cell=make('div');cell.append(make('dt',label),make('dd',value));summary.append(cell);}ticket.append(summary);content.append(ticket);
      }
      const pagination=make('div','','sb-pagination');for(const [label,target] of [['이전',data.page-1],['다음',data.page+1]]){const button=make('button',label);button.type='button';button.disabled=target<1||target>data.pages;button.onclick=()=>load(target);pagination.append(button);}pagination.prepend(make('span',data.page+' / '+data.pages));content.append(pagination);
    }catch(error){if(content.isConnected&&request===version)content.textContent=error.message||'배팅 내역을 불러오지 못했습니다.';}
  }
  source.onchange=()=>load(1);refresh.onclick=()=>load(page);await load();
}
window.addEventListener('account-changed',()=>{if(location.hash==='#/betting-history')renderBettingHistory();});
