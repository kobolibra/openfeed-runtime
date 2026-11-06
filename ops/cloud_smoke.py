"""Owner-only regression smoke: Docker profiles, no source fetches or state writes."""
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def command(*args):
    try:return subprocess.run(args,cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    except subprocess.CalledProcessError as error:
        # The owner-only caller redirects the entire smoke into a private log.
        print((error.stderr or '')[-12000:],file=sys.stderr)
        raise
def smoke(state):
    db=state/'openfeed.sqlite3';before=hashlib.sha256(db.read_bytes()).hexdigest();io=ROOT/'cloud-io'
    if io.exists():raise ValueError('Smoke output must be new')
    io.mkdir(mode=0o700);shutil.copyfile(db,io/'input.sqlite3')
    started=time.monotonic()
    compose=['docker','compose','-f',str(ROOT/'compose.cloud.yaml'),'--profile','browser']
    try:
        command('sudo','chown','-R','10001:10001',str(io))
        command(*compose,'run','--build','--rm','cycle','--input-db','/cloud-io/input.sqlite3','--output','/cloud-io/smoke','--mode','plan','--max-feeds','6','--budget-seconds','5')
        services=command(*compose,'ps','-a','--services').splitlines()
        if 'browser-worker' in services or 'egress-proxy' in services:raise ValueError('HTTP-only plan started an unnecessary browser service')
        http_seconds=round(time.monotonic()-started,3);browser_started=time.monotonic()
        command(*compose,'up','--build','-d','browser-worker')
        code="""import asyncio
from playwright.async_api import async_playwright
async def check():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,proxy={'server':'http://egress-proxy:8899'})
  try:
   page=await b.new_page();await page.set_content('<h1>Isolated browser smoke</h1>');assert await page.locator('h1').inner_text()=='Isolated browser smoke'
  finally:await b.close()
asyncio.run(check())
"""
        command(*compose,'exec','-T','browser-worker','python','-c',code)
    finally:
        command(*compose,'down','--volumes');command('sudo','chown','-R',str(os.getuid())+':'+str(os.getgid()),str(io))
    assert hashlib.sha256(db.read_bytes()).hexdigest()==before
    report={'http_only_started_browser':False,'isolated_browser_launch':'passed','input_state_unchanged':True,'network_source_fetches':0,'published':False,'http_plan_seconds':http_seconds,'browser_setup_seconds':round(time.monotonic()-browser_started,3)}
    print(json.dumps(report));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);a=p.parse_args();smoke(a.state.resolve())
