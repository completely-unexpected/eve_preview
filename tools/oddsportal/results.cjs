const {extract}=require('./collect.cjs');
const SPORT_PATHS=['football','baseball','basketball','hockey','tennis','american-football','cricket'];
function resultMetadata(){
  const context=new Map(),leagues=new Map();
  for(const a of document.querySelectorAll('a[href]')){
    const url=new URL(a.href),parts=url.pathname.split('/').filter(Boolean);
    if(parts.length===3&&parts[1]!=='h2h'&&parts[2]!=='results')context.set(parts[0],{leaguePath:url.pathname,league:a.textContent.trim()});
    if(parts[1]==='h2h'&&url.hash)leagues.set(url.hash.slice(1),context.get(parts[0])||{});
  }
  return Object.fromEntries(leagues);
}
async function collectResults(page,payload,emit){
  const sports=payload.sports;
  if(!Array.isArray(sports)||!sports.length||sports.some(sport=>!SPORT_PATHS.includes(sport)))throw Error('Invalid result sports');
  const reports=[];let count=0;
  for(const sport of [...new Set(sports)])for(const day of ['yesterday','today']){
    const url='https://www.oddsportal.com/'+sport+'/'+(day==='yesterday'?'yesterday/':'');
    emit({type:'progress',sport,day});
    try{
      const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});if(!response?.ok())throw Error('HTTP '+response?.status());
      const reject=page.getByRole('button',{name:'Reject All',exact:true});if(await reject.isVisible())await reject.click();
      await page.waitForSelector('a[href*="/h2h/"][href*="#"]',{timeout:20000});
      let complete=true;
      for(let i=0;i<100;i++){
        const more=page.getByRole('button',{name:'SHOW MORE',exact:true});if(!await more.isVisible())break;
        const previous=await page.locator('a[href*="/h2h/"][href*="#"]').count();await more.click({timeout:10000});
        try{await page.waitForFunction(n=>document.querySelectorAll('a[href*="/h2h/"][href*="#"]').length>n,previous,{timeout:10000});}catch{complete=false;break;}
        if(i===99)complete=false;
      }
      const metadata=await page.evaluate(resultMetadata);
      const date=new Date(Date.now()-(day==='yesterday'?86400000:0));const sourceDay=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul'}).format(date);
      const items=(await page.evaluate(extract)).map(item=>({...item,...metadata[item.id],sport,sourceDay}));count+=items.length;
      const report={sport,day,count:items.length,complete};reports.push(report);emit({type:'page',items,report});
    }catch(error){const report={sport,day,count:0,complete:false,error:error.message.slice(0,200)};reports.push(report);emit({type:'page',items:[],report});}
  }
  emit({type:'done',count,reports});
}
module.exports={collectResults};
if(require.main===module){require('./browser-host.cjs').request('results',{sports:JSON.parse(process.env.ODDSPORTAL_RESULT_SPORTS||'[]')},event=>process.stdout.write(JSON.stringify(event)+'\n')).catch(error=>{console.error(error.message);process.exitCode=1;});}
