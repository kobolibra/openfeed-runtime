import os,sys,subprocess
from pathlib import Path
R=Path.cwd();W=R/'work/stage3';env=dict(os.environ);env['DOCKER_HOST']='unix:///Users/time/Documents/Codex/.openfeed-colima/openfeed/docker.sock';env['DOCKER_CONFIG']=str(W/'docker-config');env['OPENFEED_ADMIN_TOKEN']=(R/'work/local-trial/source/.openfeed-local/admin-token.txt').read_text().strip();env['COMPOSE_PARALLEL_LIMIT']='2'
args=['/opt/homebrew/bin/docker-compose','-p','openfeed-live','-f',str(W/'compose.live.yaml'),*sys.argv[1:]]
raise SystemExit(subprocess.call(args,env=env))
