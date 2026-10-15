// One local browser/page shared by the periodic and administrator collectors.
// Only fixed collection operations are exposed, authenticated on loopback.
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const runtimeDir=process.env.ODDSPORTAL_RUNTIME_DIR||path.resolve(__dirname,'../../backend/.local-oddsportal-runtime');
const stateFile=path.join(runtimeDir,'host.json');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function readState(){try{const state=JSON.parse(fs.readFileSync(stateFile,'utf8'));return Number.isInteger(state.port)&&state.port>0&&state.port<65536&&/^[a-f0-9]{64}$/.test(state.token)?state:null;}catch{return null;}}
function connect(state,operation,payload,onEvent){return new Promise((resolve,reject)=>{
  const req=http.request({host:'127.0.0.1',port:state.port,path:'/'+operation,method:operation==='health'?'GET':'POST',headers:{Authorization:'Bearer '+state.token,'Content-Type':'application/json'}},res=>{
    if(res.statusCode!==200){res.resume();reject(Error('수집 브라우저 응답 오류: '+res.statusCode));return;}
    res.setEncoding('utf8');let pending='',last;
    res.on('data',chunk=>{pending+=chunk;let index;while((index=pending.indexOf('\n'))!==-1){const line=pending.slice(0,index);pending=pending.slice(index+1);if(!line)continue;try{last=JSON.parse(line);onEvent?.(last);}catch(error){req.destroy(error);}}});
    res.on('end',()=>last?.type==='fatal'?reject(Error(last.error)):resolve(last));res.on('error',reject);
  });
  req.setTimeout(operation==='health'?1500:45*60*1000,()=>req.destroy(Error('수집 브라우저 연결 제한시간 초과')));
  req.on('error',reject);req.end(operation==='health'?undefined:JSON.stringify(payload||{}));
});}
async function alive(state){if(!state)return false;try{return (await connect(state,'health')).ok===true;}catch{return false;}}
async function ensureHost(){
  let state=readState();if(await alive(state))return state;
  fs.mkdirSync(runtimeDir,{recursive:true,mode:0o700});
  const lock=path.join(runtimeDir,'launch.lock');let owns=false;
  try{fs.writeFileSync(lock,String(process.pid),{flag:'wx',mode:0o600});owns=true;}catch{
    try{if(Date.now()-fs.statSync(lock).mtimeMs>45000)fs.unlinkSync(lock);}catch{}
  }
  if(owns){try{const child=spawn(process.execPath,[__filename,'--host'],{detached:true,windowsHide:true,stdio:'ignore',env:process.env});child.unref();}catch(error){try{fs.unlinkSync(lock);}catch{}throw error;}}
  for(let i=0;i<200;i++){await sleep(150);state=readState();if(await alive(state)){if(owns){try{fs.unlinkSync(lock);}catch{}}return state;}}
  if(owns){try{fs.unlinkSync(lock);}catch{}}
  throw Error('수집 브라우저를 시작하지 못했습니다. Chrome 설치와 화면 환경을 확인해 주세요.');
}
async function request(operation,payload,onEvent){return connect(await ensureHost(),operation,payload,onEvent);}
async function host(){
  const {chromium}=require('playwright-core');
  let browser,context,page,queue=Promise.resolve();
  async function getPage(){
    if(!browser?.isConnected()){
      browser=await chromium.launch({channel:'chrome',headless:process.env.ODDSPORTAL_HEADLESS==='1',args:['--start-minimized']});
      context=await browser.newContext({viewport:{width:1280,height:720},locale:'en-US',timezoneId:'Asia/Seoul',serviceWorkers:'block'});
      page=await context.newPage();
    }else if(page.isClosed())page=await context.newPage();
    return page;
  }
  const paused=()=>fs.existsSync(path.join(runtimeDir,'paused'));
  setInterval(()=>{if(paused()&&browser?.isConnected())browser.close().catch(()=>{});},500);
  if(!paused())await getPage();
  const token=crypto.randomBytes(32).toString('hex');
  const server=http.createServer((req,res)=>{
    const auth=Buffer.from(req.headers.authorization||''),expected=Buffer.from('Bearer '+token);
    if(auth.length!==expected.length||!crypto.timingSafeEqual(auth,expected)){res.writeHead(401);res.end();return;}
    if(req.url==='/health'&&req.method==='GET'){res.writeHead(200,{'Content-Type':'application/x-ndjson'});res.end(JSON.stringify({ok:true,pid:process.pid})+'\n');return;}
    if(req.method!=='POST'||!['/collect','/today','/results'].includes(req.url)){res.writeHead(404);res.end();return;}
    let body='',tooLarge=false;
    req.on('data',chunk=>{body+=chunk;if(body.length>16384){tooLarge=true;req.destroy();}});
    req.on('end',()=>{
      if(tooLarge)return;let payload;try{payload=JSON.parse(body);}catch{res.writeHead(400);res.end();return;}
      res.writeHead(200,{'Content-Type':'application/x-ndjson','Cache-Control':'no-store'});
      const emit=value=>{if(!res.destroyed)res.write(JSON.stringify(value)+'\n');};
      // Keep queued clients alive without opening another window.
      const heartbeat=setInterval(()=>emit({type:'heartbeat'}),5000);
      queue=queue.then(async()=>{
        try{
          if(paused())throw Error('관리자가 결과 수집을 중지했습니다.');
          const activePage=await getPage();
          if(req.url==='/results')await require('./results.cjs').collectResults(activePage,payload,emit);
           else if(req.url==='/today')await require('./today.cjs').collectToday(activePage,emit,payload);
          else emit({type:'data',data:await require('./collect.cjs').collectPage(activePage,payload.pages)});
        }catch(error){emit({type:'fatal',error:error.message.slice(0,500)});}
        finally{clearInterval(heartbeat);res.end();}
      });
    });
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  fs.writeFileSync(stateFile,JSON.stringify({port:server.address().port,token,pid:process.pid}),{mode:0o600});
  async function stop(){try{if(readState()?.pid===process.pid)fs.unlinkSync(stateFile);}catch{}server.close();try{await browser?.close();}finally{process.exit(0);}}
  process.once('SIGINT',stop);process.once('SIGTERM',stop);
}
module.exports={request,readState};
if(require.main===module&&process.argv.includes('--host'))host().catch(()=>process.exit(1));
