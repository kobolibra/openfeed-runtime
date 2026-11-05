from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import pytest
from openfeed.scheduling import spread_phases,next_phase,publication_slot
from openfeed.storage import Store
from openfeed.app import choose_scheduled_feed

NOW=datetime(2026,10,26,2,0,tzinfo=timezone.utc)
def feed(i,host='example.org'):return {'id':f'{i:028x}','source_url':'https://'+host+'/list','recipe':{}}

def test_171_sources_have_even_stable_slots_and_same_site_is_interleaved():
 fs=[feed(i,'liepin.com' if i<53 else f'site{i%45}.org') for i in range(171)]
 phases=spread_phases(fs);assert phases==spread_phases(list(reversed(fs)))
 values=sorted(phases.values());gaps=[b-a for a,b in zip(values,values[1:]+[values[0]+43200])]
 assert len(set(values))==171 and min(gaps)>=252 and max(gaps)<=253
 same=sorted(phases[f['id']] for f in fs[:53]);assert max(b-a for a,b in zip(same,same[1:]+[same[0]+43200]))<=2*43200/53

def test_each_source_has_one_daytime_and_one_nighttime_slot_twelve_hours_apart():
 for phase in range(0,43200,137):
  first=next_phase(phase,720,NOW);second=next_phase(phase,720,first)
  assert first>NOW and second-first==timedelta(hours=12)
  local=[x.astimezone(ZoneInfo('Asia/Shanghai')) for x in (first,second)]
  assert sum(8<=x.hour<20 for x in local)==1

def test_manual_refresh_time_does_not_shift_the_assigned_phase():
 first=next_phase(100,720,NOW)
 assert next_phase(100,720,NOW+timedelta(minutes=20))==first
 assert next_phase(100,720,first)==first+timedelta(hours=12)

@pytest.mark.parametrize('hour,minute,allowed',[(7,59,False),(8,0,True),(12,45,True),(21,59,True),(22,0,True),(22,1,False),(23,0,False)])
def test_publisher_beijing_window_is_independent_of_machine_timezone(hour,minute,allowed):
 local=datetime(2026,10,26,hour,minute,tzinfo=ZoneInfo('Asia/Shanghai'))
 assert bool(publication_slot(local.astimezone(timezone.utc))) is allowed
 if allowed:assert publication_slot(local)==local.strftime('%Y-%m-%dT%H')

def test_spread_preserves_ids_history_status_and_paused_sources(tmp_path):
 db=Store(str(tmp_path/'state.sqlite'))
 f=db.create({'title':'Research','source_url':'https://example.org/','interval_minutes':360})
 p=db.create({'title':'Paused','source_url':'https://paused.example.org/','interval_minutes':360,'enabled':False})
 db.finish(f,[{'title':'Old','url':'https://example.org/a','summary':'','published_at':None}],None,1)
 before=db.entries(f['id']);result=db.spread_schedule(NOW);current=db.get(f['id'])
 assert result['updated']==1 and current['interval_minutes']==720
 assert current['status']=='healthy' and db.entries(f['id'])==before
 assert db.get(p['id'])['interval_minutes']==360 and not db.get(p['id'])['enabled']
 assert datetime.fromisoformat(current['next_run'])>NOW
 # Failure and manual success both retain the fixed slot, no five-minute retry storm.
 expected=next_phase(current['schedule_phase_seconds'],720)
 db.finish(current,[], 'connection failed',1)
 assert abs((datetime.fromisoformat(db.get(f['id'])['next_run'])-expected).total_seconds())<1
 db.close()

def test_new_and_imported_12h_sources_fill_gaps_without_rephasing_existing(tmp_path):
 db=Store(str(tmp_path/'state.sqlite'));one=db.create({'title':'One','source_url':'https://example.org/a'})
 phase=one['schedule_phase_seconds'];two=db.create({'title':'Two','source_url':'https://example.org/b'})
 assert one['interval_minutes']==720 and two['schedule_phase_seconds']!=phase
 db.create_many([{'title':'Three','source_url':'https://example.org/c'}]);assert db.get(one['id'])['schedule_phase_seconds']==phase
 db.update(one['id'],{'interval_minutes':360});assert db.get(one['id'])['schedule_phase_seconds'] is None
 db.close()

def test_wake_backlog_skips_busy_origin_without_starving_other_sites():
 fs=[feed(1,'a.org'),feed(2,'b.org'),feed(3,'a.org')]
 assert choose_scheduled_feed(fs,set(),{'a.org':100},101)['id']==fs[1]['id']
 assert choose_scheduled_feed(fs,{fs[1]['id']},{'a.org':100},101) is None
 assert choose_scheduled_feed(fs,set(),{'a.org':100},401)['id']==fs[0]['id']

def test_hourly_publisher_deduplicates_attempts_and_never_claims_night(tmp_path):
 from openfeed.scheduling import claim_publication_slot
 p=tmp_path/'hour.json';tz=ZoneInfo('Asia/Shanghai')
 assert not claim_publication_slot(p,datetime(2026,10,26,7,59,tzinfo=tz));assert not p.exists()
 assert claim_publication_slot(p,datetime(2026,10,26,8,0,tzinfo=tz))
 assert not claim_publication_slot(p,datetime(2026,10,26,8,59,tzinfo=tz))
 assert claim_publication_slot(p,datetime(2026,10,26,9,0,tzinfo=tz))
 assert not claim_publication_slot(p,datetime(2026,10,26,22,1,tzinfo=tz))

@pytest.mark.asyncio
async def test_schedule_migration_requires_admin_and_applies_via_api(monkeypatch,tmp_path):
 import httpx
 import openfeed.app as server
 db=Store(str(tmp_path/'state.sqlite'));monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'TOKEN','schedule-secret')
 f=db.create({'title':'Research','source_url':'https://example.org/','interval_minutes':360})
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://test') as c:
  assert (await c.post('/api/schedule/spread')).status_code==401
  r=await c.post('/api/schedule/spread',headers={'X-Admin-Token':'schedule-secret'})
  assert r.status_code==200 and r.json()['updated']==1
 assert db.get(f['id'])['interval_minutes']==720
 db.close()
