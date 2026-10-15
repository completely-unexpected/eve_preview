// Only the route is reported. No form fields or browser credentials are logged.
let navigationAuditVersion=0;
async function auditNavigation(event){
  if(document.hidden)return;
  const version=++navigationAuditVersion;
  const route=location.hash||'#/home';
  try{
    const session=await getSession();
    if(!session.authenticated||version!==navigationAuditVersion)return;
    await fetch('/api/activity/navigation/',{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':session.csrfToken},body:new URLSearchParams({route,heartbeat:event?.type==='heartbeat'?'1':'0'})});
  }catch{}
}
window.addEventListener('hashchange',auditNavigation);
window.addEventListener('account-changed',auditNavigation);
document.addEventListener('visibilitychange',auditNavigation);
setInterval(()=>auditNavigation({type:'heartbeat'}),30000);
