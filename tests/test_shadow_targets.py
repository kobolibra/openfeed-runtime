import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'ops'))
from cloud_tick import shadow_targets

def test_only_owner_shadow_bootstrap_may_select_bounded_targets():
 env={'OPENFEED_SHADOW_TARGET_IDS':'a'*24,'OPENFEED_ALLOW_SHADOW_TARGETS':'true'}
 assert shadow_targets({'mode':'shadow'},env)==['a'*24]
 for mode,allow in [('production','true'),('shadow','false')]:
  with pytest.raises(ValueError):shadow_targets({'mode':mode},{**env,'OPENFEED_ALLOW_SHADOW_TARGETS':allow})
 with pytest.raises(ValueError):shadow_targets({'mode':'shadow'},{**env,'OPENFEED_SHADOW_TARGET_IDS':'../state'})
 with pytest.raises(ValueError):shadow_targets({'mode':'shadow'},{**env,'OPENFEED_SHADOW_TARGET_IDS':','.join(format(i,'024x') for i in range(6))})
 assert shadow_targets({}, {})==[]
