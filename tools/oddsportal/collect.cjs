const fs=require('node:fs');
let chromium;
try { ({chromium}=require('playwright-core')); } catch { ({chromium}=require(process.env.ODDSPORTAL_PLAYWRIGHT_MODULE)); }
function extract() {
  const items=[];
  for(const a of document.querySelectorAll('a[href*="/h2h/"][href*="#"]')) {
    const url=new URL(a.href); if(!/^[a-zA-Z0-9]{8}$/.test(url.hash.slice(1)))continue;
    const teams=[...a.querySelectorAll('p')].filter(p=>p.classList.contains('truncate')).map(p=>p.textContent.trim());
    if(teams.length!==2 || !teams.every(Boolean))continue;
    const row=a.parentElement, group=row.parentElement.parentElement;
    const label=a.firstElementChild?.innerText.trim()||'';
    const status=/Finished|^FIN$|^After OT$|^After ET$|^After penalties$|^AET$/i.test(label)?'finished':/Postponed/i.test(label)?'postponed':/Cancelled|Canceled/i.test(label)?'cancelled':/^\d{1,2}:\d{2}$/.test(label)?'scheduled':/\d+['’]|Half|Break|Extra|Pen/i.test(label)?'live':'unknown';
    const teamGrid=a.children[1]?.firstElementChild;
    const score=part=>{const values=[...(part?.children||[])].filter(e=>e.tagName==='SPAN'&&/^\d+$/.test(e.textContent.trim()));return values.length===1?Number(values[0].textContent):null;};
    const scores=[score(teamGrid?.children[0]),score(teamGrid?.children[2])];
    const odds=[...(row.querySelector(':scope > ul')?.children||[])].map(li=>{const text=(li.querySelector('p')?.textContent||li.innerText).trim();return /^\d+(?:\.\d+)?$/.test(text)&&Number(text)>1?text:null;});
    items.push({id:url.hash.slice(1),url:url.href,home:teams[0],away:teams[1],status,statusText:label,
      scores:scores.every(n=>n!==null)?scores:null,odds,leagueText:group.firstElementChild?.innerText.trim()||'',sourcePage:location.href});
  }
  return items;
}
async function collectPage(page, configuredPages){
  const collected=new Map();
  const pages=configuredPages||JSON.parse(process.env.ODDSPORTAL_PAGES||'["https://www.oddsportal.com/"]');
  if(!Array.isArray(pages)||!pages.length||pages.length>50)throw Error('Invalid page configuration');
  for(const source of pages){const url=new URL(source);if(url.origin!=='https://www.oddsportal.com'||url.username||url.password)throw Error('Only public OddsPortal pages are allowed');
    const response=await page.goto(source,{waitUntil:'domcontentloaded',timeout:45000});
    if(!response?.ok())throw Error('OddsPortal HTTP '+response?.status());
    const reject=page.getByRole('button',{name:'Reject All',exact:true});if(await reject.isVisible())await reject.click();
    try { await page.waitForSelector('a[href*="/h2h/"][href*="#"]',{timeout:45000}); } catch(e) { console.error((await page.locator("body").innerText()).slice(0,1600)); throw e; }
    for(let i=0;i<5;i++){const more=page.getByRole('button',{name:'SHOW MORE',exact:true});if(!await more.isVisible())break;const reject=page.getByRole('button',{name:'Reject All',exact:true});if(await reject.isVisible())await reject.click();const count=await page.locator('a[href*="/h2h/"][href*="#"]').count();await more.click({timeout:10000});try{await page.waitForFunction(n=>document.querySelectorAll('a[href*="/h2h/"][href*="#"]').length>n,count,{timeout:8000});}catch{break;}}
    // Odds arrive after the match rows; wait for actual prices rather than saving loading placeholders.
    try{await page.waitForFunction(()=>[...document.querySelectorAll('a[href*="/h2h/"]')].some(a=>[...(a.parentElement.querySelector(':scope > ul')?.children||[])].some(li=>/^\d+\.\d+$/.test(li.innerText.trim()))),null,{timeout:20000});}catch{}
    for(const item of await page.evaluate(extract)){const old=collected.get(item.id);if(old&&(old.home!==item.home||old.away!==item.away))throw Error('Conflicting event identity');collected.set(item.id,item);}
  }
  const items=[...collected.values()];if(!items.length)throw Error('No match rows; existing data must be retained');
  return {source:'OddsPortal',fetchedAt:new Date().toISOString(),timezone:'Asia/Seoul',oddsLabel:'OddsPortal displayed odds; bookmaker not identified',items};
}
module.exports={extract,collectPage};
if(require.main===module){
  const pages=JSON.parse(process.env.ODDSPORTAL_PAGES||'["https://www.oddsportal.com/"]');
  require('./browser-host.cjs').request('collect',{pages}).then(result=>{
    if(result?.type!=='data')throw Error('수집 응답 형식 오류');
    process.stdout.write(JSON.stringify(result.data));
  }).catch(e=>{console.error(e.message);process.exitCode=1;});
}
