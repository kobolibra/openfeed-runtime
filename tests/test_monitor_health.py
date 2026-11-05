from openfeed.storage import Store

def test_monitor_distinguishes_paused_unhealthy_never_succeeded(tmp_path):
    db=Store(str(tmp_path/'monitor.sqlite3'))
    base='https://research.example.com/'
    fresh=db.create({'title':'Fresh','source_url':base+'fresh','interval_minutes':60})
    failed=db.create({'title':'Failed','source_url':base+'failed','interval_minutes':60})
    paused=db.create({'title':'Paused','source_url':base+'paused','enabled':False})
    never=db.create({'title':'Never','source_url':base+'never'})
    db.finish(db.get(fresh['id']),[{'title':'Paper','url':base+'paper'}],None,1)
    db.finish(db.get(failed['id']),[],'Failure',1)
    report=db.monitor()
    assert report['counts']=={'healthy':1,'stale':0,'error':1,'never_succeeded':1,'paused':1}
    assert report['total']==4
    db.close()
