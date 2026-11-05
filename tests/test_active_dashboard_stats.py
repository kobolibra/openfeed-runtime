from openfeed.storage import Store

def test_empty_active_counts_are_zero(tmp_path):
    db=Store(str(tmp_path/'empty.sqlite3'))
    assert all(db.stats()[k]==0 for k in ['active_feeds','active_healthy','active_errors','paused'])
    db.close()

def test_paused_errors_retain_history_without_becoming_active_alerts(tmp_path):
    db=Store(str(tmp_path/'state.sqlite3'))
    for n,error,paused in [(1,None,False),(2,'upstream denied',False),(3,None,True),(4,'upstream denied',True)]:
        f=db.create({'title':str(n),'source_url':f'https://example.org/{n}'})
        db.finish(f,[{'title':'Prior article','url':f'https://example.org/{n}/article','summary':'','published_at':None}],None,1)
        if error:db.finish(db.get(f['id']),[],error,1)
        if paused:db.update(f['id'],{'enabled':False})
        if error and paused:
            assert db.get(f['id'])['last_error']=='upstream denied'
            assert len(db.entries(f['id']))==1
    s=db.stats()
    assert s['feeds']==4 and s['items']==4
    assert s['healthy']==2 and s['errors']==2
    assert s['active_feeds']==2 and s['active_healthy']==1 and s['active_errors']==1 and s['paused']==2
    db.close()
