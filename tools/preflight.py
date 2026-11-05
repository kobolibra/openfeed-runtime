"""Deployment preflight: read-only checks, never claims live-site success.

Run: python tools/preflight.py --json
Exit nonzero when required local production prerequisites are absent.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import shutil
import socket
from urllib.parse import urlsplit


def inspect_environment(environ=None, *, which=shutil.which, resolver=socket.getaddrinfo):
    env=os.environ if environ is None else environ
    public=env.get('OPENFEED_PUBLIC_URL','http://localhost:8765').strip()
    parsed=urlsplit(public)
    token=env.get('OPENFEED_ADMIN_TOKEN','')
    checks={
        'admin_token':{'ok':len(token)>=24 and token.lower() not in {'changeme','example','password','your-token'},'detail':'Set a strong OPENFEED_ADMIN_TOKEN (24+ characters).'},
        'public_https':{'ok':parsed.scheme=='https' and bool(parsed.hostname),'detail':'Reader requires a stable publicly reachable HTTPS URL. This check only verifies URL shape, not actual reachability.'},
        'docker_cli':{'ok':bool(which('docker')),'detail':'Docker CLI is present, but this does not prove engine availability or build success.'},
        'chromium':{'ok':bool(which('chromium') or which('chromium-browser')),'detail':'Chromium executable exists; browser extension and Playwright require independent end-to-end tests.'},
        'browser_disabled_by_default':{'ok':env.get('OPENFEED_EXPERIMENTAL_BROWSER','0')!='1','detail':'Unisolated browser scraping must stay disabled. A configuration flag is not network isolation.'},
    }
    # A DNS probe informs test readiness, not whether specific target sites work.
    try:
        resolver('example.com',443,type=socket.SOCK_STREAM)
        checks['dns']={'ok':True,'detail':'General DNS lookup succeeded. Institutional source domains remain unverified.'}
    except OSError:
        checks['dns']={'ok':False,'detail':'General DNS lookup failed; no reliable live institutional fetch can be claimed from this environment.'}
    blockers=[key for key in ('admin_token','public_https','browser_disabled_by_default') if not checks[key]['ok']]
    return {'checks':checks,'local_prerequisites_ok':not blockers and all(c['ok'] for c in checks.values()),'production_go':False,'blockers':blockers,'note':'Preflight alone does not qualify the deployment as production safe; also validate firewall, Docker, Reader subscription, backups and live source refreshes.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json',action='store_true');args=parser.parse_args()
    data=inspect_environment()
    print(json.dumps(data,ensure_ascii=False,indent=2) if args.json else '\n'.join(f'{"OK" if v["ok"] else "MISSING"}: {k} — {v["detail"]}' for k,v in data['checks'].items()))
    raise SystemExit(0 if data['local_prerequisites_ok'] else 1)

if __name__=='__main__': main()
