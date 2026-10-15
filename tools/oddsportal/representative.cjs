// Listing prices only. No bookmaker detail requests or synthesized prices.
const fs=require('node:fs');
const {chromium}=require('playwright-core');
const {collectPage,extract}=require('./collect.cjs');
(async()=>{
  const config=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  if(!/^[a-z-]+$/.test(config.sport)||!/^\d{8}$/.test(config.day))throw Error('Invalid listing configuration');
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const context=await browser.newContext({locale:'en-US',timezoneId:'Asia/Seoul',serviceWorkers:'block'});
    const page=await context.newPage();
    const result=await collectPage(page,[`https://www.oddsportal.com/matches/${config.sport}/${config.day}/`]);
    const more=page.getByRole('button',{name:'SHOW MORE',exact:true});
    const deadline=Date.now()+180000;
    while(await more.isVisible()){
      if(Date.now()>deadline)throw Error('Listing is incomplete; existing data retained');
      const count=await page.locator('a[href*="/h2h/"][href*="#"]').count();
      await more.click({timeout:10000});
      await page.waitForFunction(n=>document.querySelectorAll('a[href*="/h2h/"][href*="#"]').length>n,count,{timeout:15000});
    }
    result.items=await page.evaluate(extract);
    fs.writeFileSync(process.argv[3],JSON.stringify(result.items));
  }finally{await browser.close();}
})().catch(e=>{console.error('Error: '+e.message);process.exitCode=1;});
