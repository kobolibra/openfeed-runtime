/* OpenFeed visual selector helpers: only used on sanitized same-origin srcdoc. */
(() => {
  'use strict';
  function classes(el) {
    return [...el.classList].filter(x => /^[A-Za-z][\w-]{1,42}$/.test(x) && !/(active|hover|selected|focus|of-selected|css-|\d{5,})/i.test(x));
  }
  function simple(el, withClass=true) {
    const tag=el.tagName.toLowerCase();
    return tag + (withClass ? classes(el).slice(0,2).map(c=>'.'+CSS.escape(c)).join('') : '');
  }
  function safeQuery(doc,rule) {
    try {return [...doc.querySelectorAll(rule)];} catch {return [];}
  }
  function realItems(nodes) {
    return nodes.filter(n=>n.querySelector('a[data-original-href],a[href]') && n.textContent.trim().length>18);
  }
  function chooseItem(target,doc) {
    const candidates=[];
    let node=target;
    while(node && node.tagName && !['BODY','HTML'].includes(node.tagName)) {
      const own=simple(node);
      for (const rule of [...new Set([own,simple(node,false)])]) {
        for(const scope of ['', node.closest('main')?'main ':'']) {
          const selector=scope+rule, found=realItems(safeQuery(doc,selector));
          if(found.length>=2 && found.length<=150 && found.includes(node)) {
            let score=found.length>40?0:1;
            if(node.tagName==='ARTICLE')score+=10;
            if(node.tagName==='LI')score+=5;
            if(classes(node).length)score+=3;
            if(scope)score+=2;
            // Prefer the nearest repeated article card, rather than a whole section.
            score+=Math.min(5,found.filter(n=>n.querySelector('h1,h2,h3,h4')).length/2);
            candidates.push({element:node,selector,count:found.length,score});
          }
        }
      }
      node=node.parentElement;
    }
    candidates.sort((a,b)=>b.score-a.score);
    if(candidates.length)return candidates[0];
    const fallback=target.closest('article,li,section,div')||target;
    return {element:fallback,selector:simple(fallback),count:safeQuery(doc,simple(fallback)).length,score:0};
  }
  function chooseField(target, field, itemSelector,doc) {
    if(field==='link') target=target.closest('a')||target.querySelector('a')||target;
    const all=safeQuery(doc,itemSelector);
    const parent=target.closest(itemSelector)||all.find(n=>n.contains(target));
    if(!parent)return {selector:simple(target)+(field==='link'?'@href':''),count:0};
    const path=[];let node=target;
    while(node&&node!==parent&&path.length<5) {path.unshift(node);node=node.parentElement;}
    const variants=[];
    for(let start=0;start<path.length;start++) {
      const sliced=path.slice(start);
      for(const withClass of [true,false]) {
        const selector=sliced.map(n=>simple(n,withClass)).join(' > ');
        const matches=all.filter(n=>safeQuery(n,selector).length>0).length;
        if(matches)variants.push({selector,matches, depth:sliced.length,withClass});
      }
    }
    variants.sort((a,b)=>{
      // A field should match across as many sibling article cards as possible.
      const av=a.matches===all.length?100+a.matches:a.matches;
      const bv=b.matches===all.length?100+b.matches:b.matches;
      return bv-av||a.depth-b.depth||Number(b.withClass)-Number(a.withClass);
    });
    let rule=variants[0]?.selector||simple(target);
    if(field==='link')rule+='@href';
    else if(field==='date'&&target.tagName==='TIME')rule+='@datetime';
    return {selector:rule,count:variants[0]?.matches||0,total:all.length};
  }
  function highlightMatches(doc, itemSelector, fields={}) {
    doc.querySelectorAll('.of-selected,.of-match,.of-field-match').forEach(node=>node.classList.remove('of-selected','of-match','of-field-match'));
    const items=safeQuery(doc,itemSelector).slice(0,250);
    let selected=0;
    for(const item of items){
      item.classList.add('of-match');
      for(const rule of Object.values(fields)){
        if(!rule)continue;
        const selector=rule.replace(/@(href|datetime|src|title|content)$/,'');
        for(const el of safeQuery(item,selector).slice(0,8)) {el.classList.add('of-field-match'); selected++;}
      }
    }
    return {items:items.length,highlightedFields:selected};
  }
  function coverage(doc,itemSelector,fields={}) {
    const items=safeQuery(doc,itemSelector).slice(0,250);
    const result={total:items.length,fields:{}};
    for(const [key,rule] of Object.entries(fields)){
      if(!rule)continue;
      const selector=rule.replace(/@(href|datetime|src|title|content)$/,'');
      result.fields[key]=items.filter(item=>safeQuery(item,selector).length>0).length;
    }
    return result;
  }
  window.OpenFeedPicker={chooseItem,chooseField,highlightMatches,coverage};
})();
