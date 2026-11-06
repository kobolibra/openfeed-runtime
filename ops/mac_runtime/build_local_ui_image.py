import io,tarfile,subprocess
from pathlib import Path
base=Path('/Users/time/Documents/Codex/2026-10-22/referenced-chatgpt-conversation-this-is-an-3');src=base/'work/local-trial/source';buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w') as tar:
 for name,data in [('Dockerfile',b'FROM openfeed-live-openfeed\nCOPY local_cloud_ui.py /app/local_cloud_ui.py\n'),('local_cloud_ui.py',(src/'ops/local_cloud_ui.py').read_bytes())]:
  info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
docker=['/opt/homebrew/bin/docker','--host','unix:///Users/time/Documents/Codex/.openfeed-colima/openfeed/docker.sock'];r=subprocess.run([*docker,'build','--network=none','--pull=false','-t','openfeed-local-cloud-ui','-'],input=buf.getvalue(),capture_output=True);assert r.returncode==0,r.stderr.decode()[-1200:]
p=base/'work/stage3/compose.live.yaml';s=p.read_text();s=s.replace('    - '+str(src/'ops/local_cloud_ui.py')+':/app/local_cloud_ui.py:ro\n','');s=s.replace('    image: openfeed-live-openfeed\n','    image: openfeed-local-cloud-ui\n',1);p.write_text(s)
r=subprocess.run([str(base/'work/venv312/bin/python'),str(base/'work/stage3/live_stack.py'),'up','-d','--no-build','--no-deps','openfeed'],cwd=base,capture_output=True);assert r.returncode==0,r.stderr.decode()[-1000:];print('Local-only management image deployed from verified wrapper; no VM file-share dependency')
