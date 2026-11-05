(()=>{
  if(window.__openFeedLivePicker) return;
  window.__openFeedLivePicker=true;
  const state={item:'',fields:{},field:'item'};
  const style=document.createElement('style');
  style.textContent='.of-match{outline:2px solid #12936b!important;outline-offset:1px!important}.of-field-match{box-shadow:inset 0 -3px #f0a33b!important}.of-selected{outline:3px solid #145e46!important;outline-offset:2px!important}#openfeed-picker-banner{position:fixed!important;top:14px!important;right:14px!important;z-index:2147483647!important;background:#102e28!important;color:white!important;border-radius:10px!important;padding:12px 16px!important;font:13px system-ui!important;box-shadow:0 9px 30px #0006!important;pointer-events:none!important}';
  document.documentElement.appendChild(style);
  const banner=document.createElement('div');banner.id='openfeed-picker-banner';document.documentElement.appendChild(banner);
  const setBanner=msg=>{banner.textContent=msg;};
  function send(){
    const selection={version:1,url:location.href,title:document.title,item_selector:state.item,fields:state.fields,coverage:state.item?window.OpenFeedPicker.coverage(document,state.item,state.fields):null};
    chrome.runtime.sendMessage({type:'OPENFEED_PICKED',selection});
  }
  function onClick(e){
    if(e.target===banner) return;
    e.preventDefault();e.stopImmediatePropagation();
    let target=e.target.nodeType===1?e.target:e.target.parentElement;
    if(!target)return;
    if(state.field==='item'){
      const match=window.OpenFeedPicker.chooseItem(target,document);
      state.item=match.selector;state.fields={};
    }else{
      if(!state.item){setBanner('Select a repeated article first');return;}
      const match=window.OpenFeedPicker.chooseField(target,state.field,state.item,document);
      state.fields[state.field]=match.selector;
    }
    window.OpenFeedPicker.highlightMatches(document,state.item,state.fields);
    const c=window.OpenFeedPicker.coverage(document,state.item,state.fields);
    setBanner(`${state.field} selected · ${c.total} cards · ${Object.entries(c.fields).map(([k,v])=>`${k} ${v}/${c.total}`).join(' · ')}`);
    send();
  }
  function onKey(e){if(e.key==='Escape'){cleanup();}}
  function cleanup(){document.removeEventListener('click',onClick,true);document.removeEventListener('keydown',onKey,true);document.querySelectorAll('.of-match,.of-field-match,.of-selected').forEach(x=>x.classList.remove('of-match','of-field-match','of-selected'));banner.remove();style.remove();delete window.__openFeedLivePicker;}
  chrome.runtime.onMessage.addListener((message,_,reply)=>{
    if(message.type==='SET_FIELD'){
      state.field=message.field;
      setBanner(`OpenFeed: select ${message.field} on this page (Esc to exit)`);
      reply({ok:true});
    }
    if(message.type==='GET_PICK')reply({selection:{version:1,url:location.href,title:document.title,item_selector:state.item,fields:state.fields}});
    if(message.type==='STOP_PICKER'){cleanup();reply({ok:true});}
  });
  document.addEventListener('click',onClick,true);document.addEventListener('keydown',onKey,true);
  setBanner('OpenFeed: click a repeated article card (Esc to exit)');
})();
