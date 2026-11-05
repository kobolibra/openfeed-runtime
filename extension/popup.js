const $=id=>document.getElementById(id);
let tab;
const message=async msg=>chrome.tabs.sendMessage(tab.id,msg);
const MAX_TRANSFER=12000;
async function init(){
  [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id || !/^https?:\/\//i.test(tab.url||'')){$('status').textContent='Open a regular web page to start selecting.';return;}
  const saved=await chrome.storage.local.get('studioUrl');if(saved.studioUrl)$('studio').value=saved.studioUrl;
  try{await chrome.scripting.executeScript({target:{tabId:tab.id},files:['picker.js','content.js']});}catch(e){$('status').textContent='Cannot select on this page: '+e.message;return;}
  await refresh();
}
async function refresh(){
  if(!tab)return;
  const {lastSelection}=await chrome.storage.session.get('lastSelection');
  if(lastSelection?.url===tab.url){$('status').textContent=`${lastSelection.item_selector||'Choose article'}\n${JSON.stringify(lastSelection.fields||{})}\n${lastSelection.coverage?.total||0} matching articles`;}
}
document.querySelectorAll('[data-field]').forEach(b=>b.onclick=async()=>{try{await message({type:'SET_FIELD',field:b.dataset.field});$('status').textContent='Now click '+b.dataset.field+' on the webpage.';}catch(e){$('status').textContent=e.message;}});
$('studio').addEventListener('change',()=>chrome.storage.local.set({studioUrl:$('studio').value}));
$('send').onclick=async()=>{
  const {lastSelection}=await chrome.storage.session.get('lastSelection');
  if(!lastSelection?.item_selector || lastSelection.url!==tab?.url){$('status').textContent='Select an article card on this tab first.';return;}
  let base;
  try{
    base=new URL($('studio').value);
    const local=['localhost','127.0.0.1','[::1]'].includes(base.hostname);
    if(base.username||base.password||base.search||base.hash||base.pathname!=='/' || (base.protocol!=='https:' && !(base.protocol==='http:'&&local)))throw Error('bad');
  }catch{$('status').textContent='Use an HTTPS Studio origin (HTTP allowed only for localhost).';return;}
  const payload=encodeURIComponent(JSON.stringify(lastSelection));
  if(payload.length>MAX_TRANSFER){$('status').textContent='Selection too large. Shorten your rules, then retry.';return;}
  await chrome.storage.local.set({studioUrl:base.origin});
  await chrome.tabs.create({url:base.origin+'/#import-picker='+payload});
};
$('copy').onclick=async()=>{const {lastSelection}=await chrome.storage.session.get('lastSelection');if(lastSelection){await navigator.clipboard.writeText(JSON.stringify(lastSelection,null,2));$('status').textContent='Copied rule JSON';}};
$('stop').onclick=async()=>{try{await message({type:'STOP_PICKER'});}catch{}window.close();};
chrome.storage.onChanged.addListener(refresh);
init();
