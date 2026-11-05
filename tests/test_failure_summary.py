from datetime import datetime,timezone,timedelta
from openfeed.diagnostics import failure_summary
NOW=datetime(2026,10,25,10,0,tzinfo=timezone.utc)
def row(i,host='example.com',error='Upstream connection failed: timeout (TimeoutError)',age=0,enabled=True):
 return {'id':str(i),'enabled':enabled,'status':'error','last_error':error,'source_url':'https://'+host+'/','last_run':(NOW-timedelta(seconds=age)).isoformat()}
def test_three_recent_domains_signal_shared_issue_without_changing_status():
 rows=[row(i,f'{i}.example.com') for i in range(3)];s=failure_summary(rows,NOW)
 assert s['suspected_network_issue'] and s['error_counts']['transport']==3
 assert all(x['status']=='error' for x in rows)
def test_same_domain_or_old_failures_are_not_global_outage():
 assert not failure_summary([row(i) for i in range(5)],NOW)['suspected_network_issue']
 assert not failure_summary([row(i,f'{i}.example.com',age=7200) for i in range(3)],NOW)['suspected_network_issue']
def test_access_and_extraction_are_separate_and_paused_does_not_count():
 s=failure_summary([row(1,error='Upstream HTTP 403'),row(2,error='No valid items extracted'),row(3,enabled=False)],NOW)
 assert s['error_counts']=={'transport':0,'access':1,'extraction':1,'browser':0,'other':0}
 assert s['paused_count']==1
