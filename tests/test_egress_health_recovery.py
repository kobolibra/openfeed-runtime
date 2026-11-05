from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
s=spec_from_file_location('runtime_health',Path(__file__).parents[1]/'ops/runtime_health.py');m=module_from_spec(s);s.loader.exec_module(m)

def test_healthy_egress_needs_no_restart(monkeypatch):
 monkeypatch.setattr(m,'egress_ready',lambda:True);run=Mock();monkeypatch.setattr(m.subprocess,'run',run)
 assert m.ensure_egress()=='healthy';run.assert_not_called()

def test_unhealthy_egress_restarts_only_known_service(monkeypatch):
 ready=iter([False,False,True]);monkeypatch.setattr(m,'egress_ready',lambda:next(ready));monkeypatch.setattr(m.time,'sleep',lambda x:None);monkeypatch.setattr(m.os,'getuid',lambda:501)
 run=Mock(return_value=SimpleNamespace(returncode=0));monkeypatch.setattr(m.subprocess,'run',run)
 assert m.ensure_egress()=='recovered'
 assert run.call_args.args[0]==['launchctl','kickstart','-k','gui/501/com.time.openfeed.egress']

def test_missing_registration_uses_installed_openfeed_plist(monkeypatch):
 ready=iter([False,True]);monkeypatch.setattr(m,'egress_ready',lambda:next(ready));monkeypatch.setattr(m.os,'getuid',lambda:501)
 run=Mock(side_effect=[SimpleNamespace(returncode=1),SimpleNamespace(returncode=0)]);monkeypatch.setattr(m.subprocess,'run',run)
 assert m.ensure_egress()=='recovered'
 assert run.call_args_list[1].args[0]==['launchctl','bootstrap','gui/501','/Users/time/Library/LaunchAgents/com.time.openfeed.egress.plist']
