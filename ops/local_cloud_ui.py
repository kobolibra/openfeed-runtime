"""Loopback-only local management UI; cloud owns all automated work."""
import json,os,secrets
from contextlib import asynccontextmanager
from pathlib import Path
from starlette.responses import JSONResponse,Response
from openfeed.app import app as studio,store,batch_jobs,TOKEN,ROOT

@asynccontextmanager
async def local_lifespan(app):
    yield
    batch_jobs.close();store.close()
studio.router.lifespan_context=local_lifespan

class CloudManagementUI:
    def __init__(self,inner):self.inner=inner
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.inner(scope,receive,send)
        path=scope.get('path','');method=scope['method']
        if path=='/api/cloud-status':
            headers=dict(scope.get('headers',[]))
            if not TOKEN or not secrets.compare_digest(headers.get(b'x-admin-token',b'').decode(),TOKEN):
                return await JSONResponse({'detail':'Administrator access required'},status_code=401)(scope,receive,send)
            p=Path('/data/cloud-sync-state.json')
            state=json.loads(p.read_text()) if p.exists() else {'status':'connecting'}
            return await JSONResponse(state)(scope,receive,send)
        blocked=(path.endswith('/run') or '/batch-jobs' in path or path in ('/api/feeds/bulk-refresh','/api/schedule/spread'))
        if method not in ('GET','HEAD','OPTIONS') and blocked:
            return await JSONResponse({'detail':'抓取与刷新由云端定时执行；本机保留来源编辑管理。'},status_code=409)(scope,receive,send)
        if path=='/static/app.js':
            extra="""\n(()=>{const b=document.createElement('div');b.style.cssText='padding:10px 18px;background:#eef6ff;color:#153552;font-size:13px;position:sticky;top:0;z-index:50';document.body.prepend(b);async function s(){try{const r=await fetch('/api/cloud-status',{headers:{'X-Admin-Token':sessionStorage.getItem('openfeed-token')||''}});if(!r.ok)return;const d=await r.json();b.textContent='云端自动运行 · 本机管理 · '+(d.status==='synced'?'已同步云端状态':d.status==='pending'?'正在同步修改，请稍候':d.status==='error'?'同步未成功，修改已保留，请检查连接':'正在连接云端');}catch{b.textContent='本机管理 · 正在连接云端';}}s();setInterval(s,15000);})();"""
            return await Response((ROOT/'static/app.js').read_text()+extra,media_type='application/javascript',headers={'Cache-Control':'no-cache'})(scope,receive,send)
        async def record(message):
            if method not in ('GET','HEAD','OPTIONS') and path.startswith('/api/feeds') and message['type']=='http.response.start' and 200<=message['status']<300:
                Path('/data/cloud-sync-state.json').write_text(json.dumps({'status':'pending'}))
            await send(message)
        return await self.inner(scope,receive,record)
app=CloudManagementUI(studio)
