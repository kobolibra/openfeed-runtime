"""Start/stop the isolated local runtime and back up its authoritative database.

Runtime configuration and the admin token remain outside distributable source.
"""
import argparse,json,os,shutil,sqlite3,subprocess,time,urllib.request
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['start','stop','backup']);p.add_argument('--config',type=Path,required=True);a=p.parse_args();cfg=json.loads(a.config.read_text())
 env=dict(os.environ);env['DOCKER_HOST']=cfg['docker_host'];env['DOCKER_CONFIG']=cfg['docker_config'];env['OPENFEED_ADMIN_TOKEN']=Path(cfg['token_file']).read_text().strip()
 compose=[cfg['compose_binary'],'-p',cfg['project'],'-f',cfg['compose_file']];colima_env={**os.environ,'COLIMA_HOME':cfg['colima_home']}
 def run(args,**kw):subprocess.run(args,check=True,**kw)
 def get(path,timeout=45):
  request=urllib.request.Request('http://127.0.0.1:8765'+path,headers={'X-Admin-Token':env['OPENFEED_ADMIN_TOKEN']})
  with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=timeout) as r:return r.read()
 if a.action=='start':
  probe=subprocess.run([cfg['docker_binary'],'info'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if probe.returncode:run([cfg['colima_binary'],'start','--profile',cfg['colima_profile']],env=colima_env)
  run([*compose,'up','-d','--no-build'],env=env)
  for _ in range(40):
   try:
    if json.loads(get('/api/health',timeout=3)).get('ok'):print('OpenFeed 已启动：http://localhost:8765');return
   except Exception:pass
   time.sleep(1)
  raise RuntimeError('OpenFeed 尚未就绪，请查看容器日志')
 if a.action=='stop':
  run([*compose,'stop'],env=env);run([cfg['colima_binary'],'stop','--profile',cfg['colima_profile']],env=colima_env);print('OpenFeed 已停止，数据库与订阅保留');return
 directory=Path(cfg['backup_dir']);directory.mkdir(parents=True,exist_ok=True);base=directory/('OpenFeed-'+time.strftime('%Y%m%d-%H%M%S'));database=base.with_suffix('.sqlite3');temp=base.with_suffix('.tmp.sqlite3');temp.write_bytes(get('/api/export/database'));temp.chmod(0o600)
 db=sqlite3.connect('file:'+str(temp)+'?mode=ro',uri=True)
 try:
  assert db.execute('pragma integrity_check').fetchone()[0]=='ok';counts={'feeds':db.execute('select count(*) from feeds').fetchone()[0],'items':db.execute('select count(*) from items').fetchone()[0]}
 finally:db.close()
 temp.replace(database)
 for suffix,url in [('.recipes.json','/api/export/recipes'),('.opml','/api/export/opml')]:
  target=base.with_suffix(suffix);target.write_bytes(get(url));target.chmod(0o600)
 manifest=base.with_suffix('.json');manifest.write_text(json.dumps({'database':str(database),'integrity':'ok',**counts},ensure_ascii=False,indent=2));manifest.chmod(0o600);print('备份完成：'+str(database));print(json.dumps(counts,ensure_ascii=False))
if __name__=='__main__':main()
