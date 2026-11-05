chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  if(message.type==='OPENFEED_PICKED') {
    chrome.storage.session.set({lastSelection:message.selection}).then(()=>respond({ok:true}));
    return true;
  }
});
