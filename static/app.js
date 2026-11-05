(() => {
'use strict';
const $ = id => document.getElementById(id);
const storage = { getItem(key){try{return sessionStorage.getItem(key)}catch{return null}}, setItem(key,val){try{sessionStorage.setItem(key,val)}catch{}}, removeItem(key){try{sessionStorage.removeItem(key)}catch{}} };
const state = { token:storage.getItem('openfeed-token') || '', feeds:[], runs:[], stats:{}, publicUrl:'', query:'', filter:'all', editing:null, view:'overview', snapshot:'', preview:null, pickedField:'item', itemNode:null };
const safe = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const humanDate = s => s ? new Date(s).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : 'Never';
const ago = s => { if(!s)return 'Not checked';let m=Math.max(0,Math.round((Date.now()-new Date(s).getTime())/60000));return m<1?'Just now':m<60?m+'m ago':m<1440?Math.floor(m/60)+'h ago':Math.floor(m/1440)+'d ago'; };
function notify(message,error=false){let el=document.createElement('div');el.className='toast'+(error?' error':'');el.textContent=message;$('toasts').append(el);setTimeout(()=>el.remove(),4500);}
async function api(path,options={}){
 const headers={'X-Admin-Token':state.token};if(options.body)headers['Content-Type']='application/json';
 let r;try{r=await fetch(path,{...options,headers:{...headers,...options.headers}});}catch(e){throw Error('Cannot reach OpenFeed Studio: '+e.message)}
 if(r.status===401 || r.status===503){$('auth-overlay').classList.remove('hidden');throw Error('Access token required or server not configured')}
 if(!r.ok){let body;try{body=await r.json();}catch{};throw Error(typeof body?.detail==='string'?body.detail:'Request failed ('+r.status+')')}
 return r.json();
}
async function load(){try {let [feeds,status]=await Promise.all([api('/api/feeds'),api('/api/status')]);state.feeds=feeds;state.stats=status.stats;state.runs=status.runs;state.diagnostics=status.diagnostics||{};state.publicUrl=status.public_url||location.origin; $('auth-overlay').classList.add('hidden');render();}catch(e){if(!state.token)$('auth-overlay').classList.remove('hidden');else notify(e.message,true)}}
async function refreshVisibleFeeds(){
 const q=state.query.toLowerCase();
 const visible=state.feeds.filter(f=>(!q||(f.title+' '+f.source_url).toLowerCase().includes(q))&&(state.filter==='all'||(state.filter==='paused'?!f.enabled:(f.enabled&&f.status===state.filter))));
 const ids=visible.filter(f=>f.enabled).slice(0,30).map(f=>f.id);
 if(!ids.length){notify('No enabled feeds in the current view.',true);return;}
 const btn=$('bulk-refresh-btn');btn.disabled=true;
 try{
  const job=await api('/api/feeds/batch-jobs',{method:'POST',body:JSON.stringify({feed_ids:ids})});
  storage.setItem('openfeed-batch-id',job.id);$('batch-cancel-btn').classList.remove('hidden');
  await monitorBatch(job.id);
 }catch(e){notify(e.message,true);btn.disabled=false;btn.textContent='Refresh visible'}
}
async function monitorBatch(id){
 const btn=$('bulk-refresh-btn');btn.disabled=true;$('batch-cancel-btn').classList.remove('hidden');
 for(let n=0;n<360;n++){
  let data;
  try{data=await api('/api/feeds/batch-jobs/'+encodeURIComponent(id))}
  catch(e){notify('Batch progress unavailable: '+e.message,true);break}
  btn.textContent='Refreshing '+data.completed+'/'+data.total+'…';
  if(['completed','interrupted','cancelled'].includes(data.status)){
   const successes=data.results.filter(x=>x.result?.status==='success').length;
   const deferred=data.results.filter(x=>['busy','rate_limited'].includes(x.result?.status)).length;
   const failed=data.results.length-successes-deferred;
   notify('Batch '+data.status+': '+successes+' updated, '+deferred+' deferred, '+failed+' failed'+(data.status==='interrupted'?' (resume available)':''),data.status==='interrupted');
   if(['completed','cancelled'].includes(data.status)){storage.removeItem('openfeed-batch-id');$('batch-cancel-btn').classList.add('hidden');}
   await load();break;
  }
  await new Promise(resolve=>setTimeout(resolve,2000));
 }
 btn.disabled=false;btn.textContent='Refresh visible';
}
async function cancelActiveBatch(){const id=storage.getItem('openfeed-batch-id');if(!id)return;try{await api('/api/feeds/batch-jobs/'+encodeURIComponent(id)+'/cancel',{method:'POST'});notify('Batch cancelled');storage.removeItem('openfeed-batch-id');$('batch-cancel-btn').classList.add('hidden');}catch(e){notify(e.message,true)}}


function render(){let s=state.stats;$('nav-count').textContent=s.feeds||0;
 const zh=window.OpenFeedI18n?.language==='zh';
 const healthy=s.active_healthy??state.feeds.filter(f=>f.enabled&&f.status==='healthy').length;
 const errors=s.active_errors??state.feeds.filter(f=>f.enabled&&f.status==='error').length;
 const paused=s.paused??state.feeds.filter(f=>!f.enabled).length;
 const cards=zh?[['信息源总数',s.feeds||0,paused+' 个已暂停'],['正常更新',healthy,'仅计已启用来源'],['已保存条目',s.items||0,'历史内容保留'],['需要处理',errors,'当前刷新错误']]:[['TOTAL SOURCES',s.feeds||0,paused+' paused'],['HEALTHY FEEDS',healthy,'Enabled sources'],['COLLECTED ITEMS',s.items||0,'Stored securely'],['NEEDS ATTENTION',errors,'Active refresh errors']];
 $('stats').innerHTML=cards.map(x=>`<div class="stat-box"><div class="stat-label">${x[0]}</div><strong>${x[1]}</strong><div class="stat-sub">${x[2]}</div></div>`).join('');
 let note=$('network-health-note');
 if(!note){note=document.createElement('div');note.id='network-health-note';note.style.cssText='margin-bottom:16px;padding:14px 18px;border:1px solid #e3bd70;border-radius:12px;background:#fff8e8;color:#674b16';$('stats').after(note);}
 const diag=state.diagnostics||{};note.hidden=!diag.suspected_network_issue;
 note.textContent=zh?`多个站点连接失败：${diag.error_counts?.transport||0} 个来源出现连接中断、超时或网络不可达，涉及 ${diag.recent_transport_domains||0} 个近期失败域名。OpenFeed 的独立抓取连接需要处理；具体原因见来源错误，不能据此判定提取规则失效。历史RSS保留，自动调度仍在运行。`:`Multiple sites have connection failures: ${diag.error_counts?.transport||0} sources across ${diag.recent_transport_domains||0} recent domains. OpenFeed’s fetch connection needs attention; see source errors for details. Existing RSS is preserved and scheduling remains enabled.`;
 let browserNote=$('browser-health-note');
 if(!browserNote){browserNote=document.createElement('div');browserNote.id='browser-health-note';browserNote.style.cssText=note.style.cssText;note.after(browserNote);}
 browserNote.hidden=!(diag.error_counts?.browser);browserNote.textContent=zh?`浏览器抓取服务异常：${diag.error_counts?.browser||0} 个来源受影响；这类错误属于浏览器运行或等待失败，应检查浏览器服务运行状态。历史RSS保留。`:`Browser service failures affect ${diag.error_counts?.browser||0} sources. This is a browser runtime/wait failure, check the browser service. Existing RSS is preserved.`;
 const view=state.view;
 document.querySelectorAll('.nav-item[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===view));
 $('crumb').innerHTML='WORKSPACE <span> / </span> '+{overview:'OVERVIEW',feeds:'ALL FEEDS',activity:'ACTIVITY'}[view];
 document.querySelector('.page-hero h1').innerHTML=view==='activity'?'System activity,<br><em>at a glance.</em>':view==='feeds'?'All your sources,<br><em>in one place.</em>':'Your information,<br><em>on your terms.</em>';
 let feeds=state.feeds;const q=state.query.toLowerCase();feeds=feeds.filter(f=>(!q||(f.title+' '+f.source_url).toLowerCase().includes(q))&&(state.filter==='all'||(state.filter==='paused'?!f.enabled:(f.enabled&&f.status===state.filter))));$('feed-visible-count').textContent=feeds.length+' of '+state.feeds.length+' sources';
 $('feed-table').innerHTML=feeds.length ? `<div class="table-head"><span>SOURCE</span><span>STATUS</span><span>ARTICLES</span><span>LAST CHECKED</span><span></span></div>${feeds.map(f=>{
 let host='';try{host=new URL(f.source_url).hostname}catch{};
 let status=!f.enabled?'paused':f.status;return `<div class="feed-row" data-id="${f.id}"><div class="source-name"><span class="source-icon">${f.kind==='native'?'◉':'↗'}</span><div style="min-width:0"><strong>${safe(f.title)}</strong><small>${safe(host)}</small></div></div><div><span title="${safe((f.last_error||'')+(f.enabled&&f.next_run?' | Next check: '+humanDate(f.next_run):''))}" class="status-badge ${status==='healthy'?'':status}">${safe(status)}</span></div><div class="meta-cell">${f.item_count} items</div><div class="meta-cell">${ago(f.last_run)}</div><button class="action-dots" title="Edit source">···</button></div>`}).join('')}` : `<div class="empty"><div style="font-size:30px;color:#b8cdbd;margin-bottom:10px">◈</div>No feeds yet. Create your first source to start collecting articles.<br><button class="secondary-btn" data-action="create" style="margin-top:20px">＋ Create your first feed</button></div>`;
 $('recent-runs').innerHTML=state.runs.length?state.runs.slice(0,7).map(r=>{let f=feeds.find(x=>x.id===r.feed_id);return `<div class="run-row"><span class="run-dot ${r.status==='error'?'error':''}"></span><div class="run-main"><strong>${safe(f?.title||'Deleted feed')}</strong><small>${r.status==='success'?`${r.inserted} new / ${r.found} found`:`Failed: ${safe(r.message.slice(0,100))}`}</small></div><time>${ago(r.at)}</time></div>`}).join(''):'<div class="empty small">No refreshes yet. Your first checks will appear here.</div>';
 if(view==='activity') { document.querySelector('.page .section').style.display='none';document.querySelector('.bottom-grid').style.gridTemplateColumns='1fr';document.querySelector('.start-panel').style.display='none'; }
 else{document.querySelector('.page .section').style.display='';document.querySelector('.bottom-grid').style.gridTemplateColumns='';document.querySelector('.start-panel').style.display='';}
 if(view==='feeds')document.querySelector('.bottom-grid').style.display='none';else document.querySelector('.bottom-grid').style.display='grid';
}
function readRecipe(){return {...(state.recipeExtras||{}),mode:$('extract-mode').value,fetch_mode:$('fetch-mode').value,content_type:$('content-type').value,complete_inventory:$('complete-inventory').value==='true',wait_selector:$('wait-selector').value.trim(),item_selector:$('item-selector').value.trim(),global_pattern:$('global-pattern').value.trim(),next_selector:$('next-selector').value.trim(),max_pages:Number($('max-pages').value),min_items:Number($('min-items').value),min_dated_pct:Number($('min-dated-pct').value),fields:Object.fromEntries([['title','title-selector'],['link','link-selector'],['date','date-selector'],['summary','summary-selector']].filter(([_,id])=>$(id).value.trim()).map(([key,id])=>[key,$(id).value.trim()]))}}
function populate(f){state.recipeExtras=structuredClone(f?.recipe||{});$('src-url').value=f?.source_url||'';$('feed-title').value=f?.title||'';$('feed-interval').value=f?.interval_minutes||720;$('feed-kind').value=f?.kind||'web';$('extract-mode').value=f?.recipe?.mode||'css';$('fetch-mode').value=f?.recipe?.fetch_mode||'http';$('content-type').value=f?.recipe?.content_type||'articles';$('complete-inventory').value=String(f?.recipe?.complete_inventory===true);$('wait-selector').value=f?.recipe?.wait_selector||'';$('item-selector').value=f?.recipe?.item_selector||'';$('global-pattern').value=f?.recipe?.global_pattern||'';$('next-selector').value=f?.recipe?.next_selector||'';$('max-pages').value=f?.recipe?.max_pages||1;$('min-items').value=f?.recipe?.min_items??0;$('min-dated-pct').value=f?.recipe?.min_dated_pct??0;for(let field of ['title','link','date','summary'])$(field+'-selector').value=f?.recipe?.fields?.[field]||'';
 $('preview-results').innerHTML='<div class="preview-placeholder"><span>◈</span><strong>Preview your feed</strong><p>Test your settings to see real articles from your source.</p></div>';$('publish-result').classList.add('hidden');$('publish-result').querySelector('p').textContent='Your public RSS URL is ready for Readwise Reader once a source refresh succeeds.';$('delete-btn').classList.toggle('hidden',!f);$('toggle-btn').classList.toggle('hidden',!f);$('toggle-btn').textContent=f?.enabled?'Pause source':'Resume source';$('feed-diagnostics').classList.add('hidden');$('save-btn').textContent=f?'Save changes':'Publish feed →';$('drawer-title').textContent=f?'Edit feed':'Create a feed';state.preview=null;state.snapshot='';}
async function diagnostics(f){if(!f)return;try{const data=await api('/api/feeds/'+f.id);if(state.editing!==f.id)return;const latest=data.items.slice(0,7),runs=data.runs.slice(0,5);const revisions=await api('/api/feeds/'+f.id+'/revisions');const lifecycle=f.recipe?.content_type==='jobs'?await api('/api/feeds/'+f.id+'/lifecycle'):null;const changes=await api('/api/feeds/'+f.id+'/events');if(state.editing!==f.id)return;$('feed-diagnostics').innerHTML=`<h3>Latest extracted items</h3>${latest.length?latest.map(x=>`<div class="diag-item"><strong>${safe(x.title)}</strong><small>${safe(x.published_at||'Publication date unknown')} · <a target="_blank" rel="noopener noreferrer" href="${safe(x.url)}">Open source ↗</a></small></div>`).join(''):'<p>No articles stored yet.</p>'}<h3>Recent checks</h3>${runs.length?runs.map(r=>`<div class="diag-run"><span>${safe(r.status)} · ${ago(r.at)}</span><span>${r.inserted} new · ${r.elapsed_ms}ms</span></div>`).join(''):'<p>No checks yet.</p>'}${lifecycle?`<h3>Job inventory changes</h3>${lifecycle.items.filter(x=>x.availability!=='observed').slice(0,15).map(x=>`<div class="diag-run"><span>${safe(x.title)} · ${safe(x.availability)}</span><small>${x.missing_count} absent refreshes</small></div>`).join('')||'<p>No possible closures detected.</p>'}`:''}<h3>Content change events</h3>${changes.events.slice(0,10).map(x=>`<div class="diag-run"><span>${safe(x.event_type)} · ${safe(x.title)} · ${ago(x.at)}</span></div>`).join('')||'<p>No content changes yet.</p>'}<h3>Rule revision history</h3>${revisions.slice(0,8).map(r=>`<div class="diag-run"><span>v${r.revision} · ${safe(r.action)} · ${ago(r.changed_at)}</span><button type="button" data-restore="${r.revision}" ${r.revision===revisions[0].revision?'disabled':''}>Restore</button></div>`).join('')}`;$('feed-diagnostics').classList.remove('hidden')}catch(e){notify(e.message,true)}}
async function restoreRevision(revision){
 const id=state.editing;if(!id||!confirm(`Restore rule revision ${revision}? The current configuration will remain in revision history.`))return;
 try{const res=await api('/api/feeds/'+id+'/restore/'+revision,{method:'POST'});if(state.editing!==id)return;populate(res.feed);await load();await diagnostics(res.feed);notify(`Restored rule revision ${revision}; run a refresh to validate the source.`)}catch(e){notify(e.message,true)}
}
async function diagnoseCurrent(){
 if(!state.editing){notify('Save this feed before running rule diagnostics.',true);return;}
 try{
   const data=await api('/api/feeds/'+state.editing+'/diagnose',{method:'POST'});
   let content=`<h3>Rule health diagnosis</h3><p>Current: ${data.current_items??'-'} extracted · Stored: ${data.stored_items??'-'}</p>`;
   if(data.current_error)content+=`<p>${safe(data.current_error)}</p>`;
   content+=(data.suggestions||[]).map(c=>`<div class="diag-run"><span><strong>${safe(c.selector)}</strong> · ${c.valid_items} valid · ${c.dated} dated</span><button type="button" data-apply-suggestion="${safe(c.selector)}">Try selector</button></div>`).join('');
   content+=`<p>${safe(data.message||'')}</p>`;
   $('feed-diagnostics').innerHTML=content;$('feed-diagnostics').classList.remove('hidden');
 }catch(e){notify(e.message,true)}
}

function drawer(f=null){state.editing=f?.id||null;populate(f);$('drawer').classList.remove('hidden');$('shade').classList.remove('hidden');$('src-url').focus();if(f)diagnostics(f);}
function closeDrawer(){$('drawer').classList.add('hidden');$('shade').classList.add('hidden');}
async function inspect(){let url=$('src-url').value.trim();if(!url)return notify('Please enter a URL',true);$('test-btn').disabled=true;$('test-btn').textContent='Checking website…';
 try{let p=await api('/api/inspect',{method:'POST',body:JSON.stringify({url,recipe:readRecipe()})});state.preview=p;state.snapshot=p.snapshot||'';
 if(!state.editing && !$('feed-title').value){try{$('feed-title').value=new URL(url).hostname.replace('www.','')}catch{}}
 if(p.selector && p.selector!=='native feed' && !$('item-selector').value)$('item-selector').value=p.selector;
 let html=p.discovered?.length?`<div class="discover-box">◉ Existing feed detected${p.discovered.map((f,i)=>`<button type="button" data-native="${i}" title="Use existing RSS instead of scraping">Use official feed: ${safe(f.title)} →</button>`).join('')}</div>`:'';
 if(p.candidates?.length){html+=`<div class="candidate-heading">Suggested article containers <span>Click to apply & test</span></div><div class="candidate-list">${p.candidates.slice(0,5).map((c,i)=>`<button type="button" class="candidate-choice" data-candidate="${i}"><span><strong>${safe(c.selector)}</strong><small>${safe(c.sample_titles?.[0]||'')}</small></span><b>${c.count} items</b></button>`).join('')}</div>`;}
 html+=p.preview_items?.length?`<div class="preview-result-head"><span>✓ ${p.preview_items.length} articles extracted</span><span>PREVIEW</span></div>${p.preview_items.slice(0,12).map(x=>`<div class="preview-item"><strong>${safe(x.title)}</strong><small>${safe(x.published_at||'Date not available')} · ${safe(x.url)}</small></div>`).join('')}`:`<div class="empty">${safe(p.error||'No articles found. Try manual selectors or native RSS mode.')}</div>`;
 if(p.warnings?.length){html+=`<div class="inspect-warnings">${p.warnings.map(x=>`<p>⚠ ${safe(x)}</p>`).join('')}</div>`;}
 $('preview-results').innerHTML=html;notify('Website inspection complete');
 }catch(e){notify(e.message,true);$('preview-results').innerHTML='<div class="empty">'+safe(e.message)+'</div>'}finally{$('test-btn').disabled=false;$('test-btn').textContent='◎ Test extraction'} }
async function save(){let src=$('src-url').value.trim(),title=$('feed-title').value.trim();if(!src)return notify('Enter a source URL',true);if(!title)return notify('Enter a feed name',true);
 let data={title,source_url:src,kind:$('feed-kind').value,interval_minutes:Number($('feed-interval').value),recipe:readRecipe()};$('save-btn').disabled=true;$('save-btn').textContent='Saving…';
 try{let f=await api(state.editing?'/api/feeds/'+state.editing:'/api/feeds',{method:state.editing?'PATCH':'POST',body:JSON.stringify(data)});state.editing=f.id;let link=(state.publicUrl||location.origin)+'/rss/'+f.id+'.xml';$('created-link').value=link;$('open-created').href=link;$('publish-result').classList.remove('hidden');$('save-btn').textContent='Saved ✓';$('delete-btn').classList.remove('hidden');notify('Feed saved. Running first refresh…');const res=await api('/api/feeds/'+f.id+'/run',{method:'POST'});if(res.status==='error'){$('publish-result').querySelector('p').textContent='Feed saved, but the source fetch failed. The published feed keeps any previously stored items.';notify('Saved, but refresh failed: '+res.message,true)}else if(res.status==='success'){$('publish-result').querySelector('p').textContent='Validated and refreshed. Use the public HTTPS URL in Readwise Reader.';notify(res.found+' articles, '+res.inserted+' new')}else{$('publish-result').querySelector('p').textContent='Feed saved. Refresh is deferred by source rate limits.';notify('Refresh deferred: '+res.status,true)}await load();await diagnostics(f);}
 catch(e){notify(e.message,true)}finally{$('save-btn').disabled=false;$('save-btn').textContent='Save changes'} }
async function remove(){if(!state.editing||!confirm('Delete this feed and its stored items? This cannot be undone.'))return;try{await api('/api/feeds/'+state.editing,{method:'DELETE'});closeDrawer();load();notify('Feed deleted')}catch(e){notify(e.message,true)}}
async function download(path){try{const response=await fetch(path,{headers:{'X-Admin-Token':state.token}});if(!response.ok)throw Error('Export failed');let blob=await response.blob();let filename=path.includes('opml')?'openfeed.opml':path.includes('database')?'openfeed-backup.sqlite3':'openfeed-recipes.json';let link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);notify(filename+' exported')}catch(e){notify(e.message,true)}}
async function toggleSource(){if(!state.editing)return;try{const f=state.feeds.find(x=>x.id===state.editing);const changed=await api('/api/feeds/'+f.id,{method:'PATCH',body:JSON.stringify({enabled:!f.enabled})});$('toggle-btn').textContent=changed.enabled?'Pause source':'Resume source';await load();notify(changed.enabled?'Source resumed':'Source paused')}catch(e){notify(e.message,true)}}
function showExport(){$('migration').classList.remove('hidden')}
let uploadKind='recipes';
async function importFile(file){if(!file)return;try{const response=await fetch('/api/import/'+uploadKind,{method:'POST',headers:{'X-Admin-Token':state.token,'Content-Type':uploadKind==='opml'?'application/xml':'application/json'},body:await file.text()});const data=await response.json();if(!response.ok)throw Error(data.detail||'Import failed');notify(`Imported ${data.imported} feeds; skipped ${data.skipped}.`);$('migration').classList.add('hidden');await load();}catch(e){notify(e.message,true)}finally{$('import-file').value=''}}
function pickInspect(){
 if(!state.snapshot)return notify('Test a web page first to load a safe snapshot',true);
 if($('extract-mode').value==='xpath'||$('extract-mode').value==='pattern'||$('extract-mode').value==='json'||$('extract-mode').value==='pdf')return notify('Visual picker generates CSS. Switch to CSS mode first.',true);
 if(!window.OpenFeedPicker)return notify('Picker component was not loaded',true);
 state.pickedField='item';state.itemNode=null;
 document.querySelectorAll('.picker-fields button').forEach(b=>b.classList.toggle('chosen',b.dataset.field==='item'));
 $('picked-selector').textContent='Click an element to begin';$('inspector').classList.remove('hidden');$('shade').classList.remove('hidden');
 const frame=$('snapshot');
 frame.onload=()=>{
  const doc=frame.contentDocument;if(!doc)return;
  const style=doc.createElement('style');style.textContent='.of-match{outline:2px solid #4aaf75!important;outline-offset:-2px!important;background:rgba(74,175,117,.065)!important}.of-field-match{box-shadow:inset 0 -3px #e9b653!important}.of-selected{outline:3px solid #145e46!important;outline-offset:2px!important}';doc.head.appendChild(style);
  doc.addEventListener('click',event=>{
   event.preventDefault();event.stopPropagation();
   let target=event.target.nodeType===1?event.target:event.target.parentElement;
   if(!target)return;
   doc.querySelectorAll('.of-selected').forEach(e=>e.classList.remove('of-selected'));
   const field=state.pickedField;let result;
   if(field==='item'){
    result=window.OpenFeedPicker.chooseItem(target,doc);
    state.itemNode=result.element;
    $('item-selector').value=result.selector;
   }else{
    const selector=$('item-selector').value.trim();
    if(!selector)return notify('Select an item container first',true);
    result=window.OpenFeedPicker.chooseField(target,field,selector,doc);
    $(field+'-selector').value=result.selector;
   }
   const itemSelector=$('item-selector').value.trim();
   const fieldRules=Object.fromEntries(['title','link','date','summary'].map(k=>[k,$(k+'-selector').value.trim()]));
   const stats=window.OpenFeedPicker.coverage(doc,itemSelector,fieldRules);
   window.OpenFeedPicker.highlightMatches(doc,itemSelector,fieldRules);
   (result.element||target).classList.add('of-selected');
   $('picked-selector').textContent=result.selector;
   const fieldStats=Object.entries(stats.fields).map(([k,n])=>`${k}: ${n}/${stats.total}`).join(' · ');
   $('picked-count').textContent=stats.total+' article containers highlighted'+(fieldStats?' · '+fieldStats:'');
  },true);
 };
 frame.srcdoc=state.snapshot;
}
function closeInspect(){$('inspector').classList.add('hidden');$('shade').classList.remove('hidden');}
function wire(){
 $('feed-search').addEventListener('input',e=>{state.query=e.target.value.trim();render()});$('feed-filter').addEventListener('change',e=>{state.filter=e.target.value;render()});$('toggle-btn').onclick=toggleSource;$('feed-diagnostics').addEventListener('click',e=>{const target=e.target.closest('[data-restore]');if(target&&!target.disabled)restoreRevision(Number(target.dataset.restore))});$('feed-diagnostics').addEventListener('click',e=>{const t=e.target.closest('[data-apply-suggestion]');if(t){$('item-selector').value=t.dataset.applySuggestion;notify('Suggested item selector inserted. Run Test extraction before saving.')}});
 document.body.addEventListener('click',e=>{let action=e.target.closest('[data-action]')?.dataset.action;if(action==='create')drawer();else if(action==='import')showExport();let view=e.target.closest('[data-view]')?.dataset.view;if(view){state.view=view;render()};let row=e.target.closest('.feed-row');if(row){let f=state.feeds.find(x=>x.id===row.dataset.id);if(f)drawer(f)}});
 $('preview-results').addEventListener('click',e=>{
  const native=e.target.closest('[data-native]');if(native){const f=state.preview?.discovered?.[Number(native.dataset.native)];if(f){$('src-url').value=f.url;$('feed-kind').value='native';$('item-selector').value='';notify('Using the original RSS feed; no extraction rule required.');return;}}
  const b=e.target.closest('[data-candidate]');if(!b)return;
  const c=state.preview?.candidates?.[Number(b.dataset.candidate)];if(!c)return;
  $('extract-mode').value='css';$('item-selector').value=c.selector;
  if(!$('title-selector').value)$('title-selector').value=c.fields?.title||'';
  if(!$('link-selector').value)$('link-selector').value=c.fields?.link||'';
  notify('Suggested rule applied. Re-test to validate extracted articles.');
 });
 $('view-all').onclick=()=>{state.view='feeds';render()};
 $('migration-close').onclick=()=>$('migration').classList.add('hidden');
 document.querySelectorAll('[data-export]').forEach(b=>b.onclick=()=>download('/api/export/'+b.dataset.export));
 document.querySelectorAll('[data-upload]').forEach(b=>b.onclick=()=>{uploadKind=b.dataset.upload;$('import-file').click()});
 $('import-file').onchange=e=>importFile(e.target.files?.[0]);
 $('extract-mode').onchange=()=>{$('rule-help').textContent=$('extract-mode').value==='pattern'?'Feed43 mode: use {%} capture and {*} ignore. Title/Link/Date/Summary selectors are capture numbers such as 2, 1, 3, 4.':$('extract-mode').value==='pdf'?'PDF: find links ending in .pdf; item selector may scope cards or links (a[href]). Each document becomes an RSS item.':$('extract-mode').value==='json'?'JSON API: item path is a dotted array path such as data.items; field selectors are relative paths such as headline, permalink, published_at.':$('extract-mode').value==='xpath'?'XPath: item is //article, fields are relative XPath such as (.//h2/text())[1].':'CSS: item container can be auto-detected; fields are relative CSS selectors such as h2, a@href, time.'};$('close-drawer').onclick=closeDrawer;$('shade').onclick=()=>{if(!$('inspector').classList.contains('hidden'))closeInspect();else closeDrawer()};$('test-btn').onclick=inspect;$('diagnose-btn').onclick=diagnoseCurrent;$('save-btn').onclick=save;$('delete-btn').onclick=remove;
 $('copy-created').onclick=()=>navigator.clipboard.writeText($('created-link').value).then(()=>notify('RSS URL copied'));
 $('visual-btn').onclick=pickInspect;$('inspector-close').onclick=closeInspect;
 document.querySelectorAll('.picker-fields button').forEach(b=>b.onclick=()=>{state.pickedField=b.dataset.field;document.querySelectorAll('.picker-fields button').forEach(x=>x.classList.toggle('chosen',x===b))});
 $('language-toggle').onclick=()=>{window.OpenFeedI18n?.toggle();render()};$('lock').onclick=()=>{state.token='';storage.removeItem('openfeed-token');$('auth-token').value='';state.feeds=[];state.runs=[];state.stats={};$('auth-overlay').classList.remove('hidden')};$('auth-form').onsubmit=e=>{e.preventDefault();state.token=$('auth-token').value;storage.setItem('openfeed-token',state.token);load()};
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('inspector').classList.add('hidden');$('migration').classList.add('hidden');closeDrawer()}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();drawer()}});
}
function importPickerHash(){
  const prefix='#import-picker=';
  if(!location.hash.startsWith(prefix))return;
  try {
    const data=JSON.parse(decodeURIComponent(location.hash.slice(prefix.length)));
    if(data.version!==1 || typeof data.url!=='string' || !['http:','https:'].includes(new URL(data.url).protocol) || data.url.length>2048 || typeof data.item_selector!=='string' || data.item_selector.length>500)throw Error('Invalid picker data');
    const rules=data.fields||{};
    if(typeof rules!=='object'||Array.isArray(rules)||Object.keys(rules).some(k=>!['title','link','date','summary'].includes(k))||Object.values(rules).some(x=>typeof x!=='string'||x.length>500))throw Error('Invalid selector');
    drawer();$('src-url').value=data.url;$('feed-title').value=(data.title||new URL(data.url).hostname).slice(0,180);
    $('extract-mode').value='css';$('item-selector').value=data.item_selector;
    for(const k of ['title','link','date','summary'])$(k+'-selector').value=rules[k]||'';
    notify('Live website selection imported. Test extraction before publishing.');
  }catch(e){notify('Cannot import browser selection: '+e.message,true);}
  finally{history.replaceState(null,'',location.pathname+location.search);}
}
wire();$('bulk-refresh-btn').onclick=refreshVisibleFeeds;$('batch-cancel-btn').onclick=cancelActiveBatch;window.OpenFeedI18n?.apply();load().then(async()=>{const id=storage.getItem('openfeed-batch-id');if(id){try{const job=await api('/api/feeds/batch-jobs/'+encodeURIComponent(id));if(job.status==='interrupted'){if(confirm('An interrupted bulk refresh was found. Resume its remaining sources?')){await api('/api/feeds/batch-jobs/'+encodeURIComponent(id)+'/resume',{method:'POST'});monitorBatch(id)}else{notify('Batch interrupted; reload to resume.',true)}}else if(['pending','running'].includes(job.status))monitorBatch(id);else storage.removeItem('openfeed-batch-id')}catch(e){notify('Could not restore batch progress: '+e.message,true)}}});importPickerHash();
})();
