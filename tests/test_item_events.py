from openfeed.storage import Store


def test_job_events_are_durable_and_do_not_repeat(tmp_path):
    db=Store(str(tmp_path/'events.sqlite3'))
    feed=db.create({'title':'Jobs','source_url':'https://jobs.example/list',
                    'recipe':{'content_type':'jobs','complete_inventory':True}})
    url='https://jobs.example/job/1';other='https://jobs.example/job/2'
    def refresh(items,error=None):
        return db.finish(db.get(feed['id']),[{'title':title,'url':link} for title,link in items],error,1)
    refresh([('Analyst',url),('Manager',other)])
    refresh([('Analyst',url)])
    refresh([('Analyst',url)])
    assert [e['event_type'] for e in db.item_events(feed['id'])[:2]]==['possibly_closed','missing_once']
    refresh([('Senior Analyst',url),('Manager',other)])
    events=db.item_events(feed['id'])
    assert events[0]['event_type']=='reappeared'
    assert events[1]['event_type']=='updated'
    before=len(events)
    refresh([('Senior Analyst',url),('Manager',other)])
    assert len(db.item_events(feed['id']))==before
    refresh([],error='Network error')
    assert len(db.item_events(feed['id']))==before
    db.close()


def test_existing_sqlite_store_migrates_events_additively(tmp_path):
    db=Store(str(tmp_path/'database.sqlite3'))
    feed=db.create({'title':'Reports','source_url':'https://research.example/list'})
    db.close()
    restored=Store(str(tmp_path/'database.sqlite3'))
    assert restored.get(feed['id'])['id']==feed['id']
    assert restored.item_events(feed['id'])==[]
    restored.close()
