"""Restore only the already configured OpenFeed egress service."""
import os,socket,subprocess,time
from pathlib import Path

def egress_ready():
 try:
  with socket.create_connection(('127.0.0.1',8900),timeout=1):return True
 except OSError:return False

def ensure_egress():
 if egress_ready():return 'healthy'
 domain=f'gui/{os.getuid()}';label=domain+'/com.time.openfeed.egress'
 result=subprocess.run(['launchctl','kickstart','-k',label],capture_output=True,timeout=10)
 if result.returncode:
  # Load the installed, user-owned configuration; never derive a proxy from VPN settings.
  plist=Path('/Users/time/Library/LaunchAgents/com.time.openfeed.egress.plist')
  subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True,capture_output=True,timeout=10)
 for _ in range(10):
  if egress_ready():return 'recovered'
  time.sleep(.5)
 raise RuntimeError('OpenFeed dedicated egress did not start; existing RSS preserved')
