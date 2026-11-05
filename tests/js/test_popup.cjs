const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const code=fs.readFileSync(require('node:path').join(__dirname,'../../extension/popup.js'),'utf8');
const item={version:1,url:'https://example.org/articles',item_selector:'article',fields:{title:'h2',link:'a@href'}};
async function setup(studio){
 const elements={}; const opened=[];let saved={studioUrl:studio};
 const get=id=>elements[id]??(elements[id]={value:id==='studio'?studio:'',textContent:'',dataset:{},addEventListener(){}});
 const chrome={tabs:{query:async()=>[{id:5,url:item.url}],sendMessage:async()=>{},create:async x=>opened.push(x.url)},scripting:{executeScript:async()=>{}},storage:{local:{get:async()=>saved,set:async x=>{saved={...saved,...x}}},session:{get:async()=>({lastSelection:item})},onChanged:{addListener(){}}}};
 const document={getElementById:get,querySelectorAll:()=>[]};
 const context={chrome,document,URL,JSON,encodeURIComponent,navigator:{clipboard:{writeText:async()=>{}}},window:{close(){}}};
 vm.createContext(context);vm.runInContext(code,context);
 await new Promise(r=>setImmediate(r));
 get('studio').value=studio;await get('send').onclick();return {opened,elements};
}
test('allows local Studio transfer',async()=>{const a=await setup('http://localhost:8765/');assert.equal(a.opened.length,1);assert.match(a.opened[0],/^http:\/\/localhost:8765\/#import-picker=/);});
test('rejects forwarding selectors to remote plaintext Studio',async()=>{const a=await setup('http://attacker.invalid/');assert.equal(a.opened.length,0);assert.match(a.elements.status.textContent,/HTTPS/);});
test('rejects Studio URLs with query parameters',async()=>{const a=await setup('https://studio.example/?external=1');assert.equal(a.opened.length,0);});
test('allows HTTPS Studio origin',async()=>{const a=await setup('https://feeds.example.org/');assert.equal(a.opened.length,1);});
