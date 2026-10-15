
const {extract}=require('./collect.cjs');
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n');
const day=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(new Date());
async function consent(page){const reject=page.locator('#onetrust-reject-all-handler');if(await reject.isVisible())await reject.click({timeout:5000});}
async function discover(page,emit){
  await page.goto('https://www.oddsportal.com/football/',{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForSelector('aside [role="button"] img[src*="/sport_icons/"]',{timeout:30000});
  const names=await page.locator('aside [role="button"] img[src*="/sport_icons/"]').evaluateAll(imgs=>[...new Set(imgs.map(i=>i.alt).filter(Boolean))]);
  if(!names.length)throw Error('종목 메뉴를 찾지 못했습니다.');
  const sports=[],reports=[];
  for(const name of names){
    emit({type:'discovery',sport:name});
    try{
      await consent(page);
      const button=page.locator('aside [role="button"]').filter({has:page.locator('img[alt='+JSON.stringify(name)+']')}).first();
      let href=await button.evaluate(el=>el.closest('li')?.querySelector('a[href^="/matches/"]')?.getAttribute('href'));
      if(!href){await button.click({timeout:5000});await page.waitForFunction(name=>[...document.querySelectorAll('aside [role="button"] img')].find(i=>i.alt===name)?.closest('li')?.querySelector('a[href^="/matches/"]'),name,{timeout:5000});href=await button.evaluate(el=>el.closest('li')?.querySelector('a[href^="/matches/"]')?.getAttribute('href'));}
      if(!href)throw Error('오늘 경기 링크 없음');
      sports.push({name,url:new URL(href,'https://www.oddsportal.com').href});
    }catch(e){reports.push({sport:name,count:0,complete:false,error:e.message.slice(0,300)});}
  }
  return {sports:[...new Map(sports.map(s=>[s.url,s])).values()],reports};
}
async function collectToday(page,emit,options={}){
    let {sports,reports}=await discover(page,emit);
    if(options.sport&&options.sport!=='all'){
      const slug=options.sport==='ice-hockey'?'hockey':options.sport;
      sports=sports.filter(s=>new URL(s.url).pathname.split('/').includes(slug));
      reports=reports.filter(r=>r.sport===options.sport);
    }
    if(!sports.length)throw Error('오늘 경기 종목 목록을 찾지 못했습니다.');
    emit({type:'plan',total:sports.length,reports});
    const collectionDay=day();let completed=0;const ids=new Set();
    for(const sport of sports){
      emit({type:'progress',sport:sport.name,completed,total:sports.length});
      try{
        if(day()!==collectionDay)throw Error('수집 중 날짜가 바뀌었습니다. 다시 수집해 주세요.');
        const url=new URL(sport.url);if(url.origin!=='https://www.oddsportal.com'||url.username||url.password)throw Error('허용되지 않은 수집 주소');
        const response=await page.goto(url.href,{waitUntil:'domcontentloaded',timeout:45000});if(!response?.ok())throw Error('HTTP '+response?.status());
        await consent(page);
        await page.waitForFunction(()=>document.querySelector('a[href*="/h2h/"][href*="#"]')||/no (?:matches|events|games)|there are no/i.test(document.body.innerText),null,{timeout:30000});
        const more=page.getByRole('button',{name:/^show more$/i});let complete=true;const deadline=Date.now()+180000;
        for(let clicks=0;clicks<1000;clicks++){
          if(!await more.isVisible())break;
          if(Date.now()>deadline){complete=false;break;}
          await consent(page);const count=await page.locator('a[href*="/h2h/"][href*="#"]').count();await more.click({timeout:10000});
          try{await page.waitForFunction(n=>document.querySelectorAll('a[href*="/h2h/"][href*="#"]').length>n||![...document.querySelectorAll('button')].some(b=>/^show more$/i.test(b.textContent.trim())&&b.getClientRects().length),count,{timeout:15000});}catch{complete=false;break;}
        }
        if(await more.isVisible())complete=false;
        let items=await page.evaluate(extract);
        if(items.length){try{await page.waitForFunction(()=>[...document.querySelectorAll('a[href*="/h2h/"]')].some(a=>[...(a.parentElement.querySelector(':scope > ul')?.children||[])].some(li=>/^\d+\.\d+$/.test(li.innerText.trim()))),null,{timeout:15000});}catch{}items=await page.evaluate(extract);}
        if(!items.length&&!/no (?:matches|events|games)|there are no/i.test(await page.locator('body').innerText()))throw Error('경기 행을 읽지 못했습니다.');
        for(const item of items){item.sport=sport.name;item.collectionDay=collectionDay;item.observedAt=new Date().toISOString();ids.add(item.id);}
        const report={sport:sport.name,url:sport.url,count:items.length,complete,error:complete?'':'더 보기 목록이 남아 있어 일부만 수집됐습니다.'};reports.push(report);completed++;
        emit({type:'page',sport:sport.name,completed,total:sports.length,items,report,collectionDay,timezone:'Asia/Seoul'});
      }catch(e){completed++;const report={sport:sport.name,url:sport.url,count:0,complete:false,error:e.message.slice(0,300)};reports.push(report);emit({type:'page',sport:sport.name,completed,total:sports.length,items:[],report,collectionDay,timezone:'Asia/Seoul'});}
    }
    emit({type:'done',count:ids.size,reports});

}
module.exports={collectToday};
if(require.main===module)require('./browser-host.cjs').request('today',{sport:process.env.ODDSPORTAL_SPORT||'all'},emit).catch(e=>{emit({type:'fatal',error:e.message.slice(0,500)});process.exitCode=1;});
