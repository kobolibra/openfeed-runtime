"""Single-instance SQLite repository. WAL and transactions preserve the last known good Feed."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import json
import os
import secrets
import sqlite3
import threading
from .extract import guid_for
from .scheduling import next_phase, spread_phases

def same_fetch_identity(before: dict,after: dict) -> bool:
    """A display-page correction is safe only when the actual fetch stays exact."""
    if before.get('kind','web')!='web' or after.get('kind','web')!='web':return False
    def target(feed):return (feed.get('recipe') or {}).get('fetch_url') or feed['source_url']
    return target(before)==target(after)


def source_identity_changed(before: dict,after: dict) -> bool:
    if before.get('kind','web')=='web' and after.get('kind','web')=='web':
        return not same_fetch_identity(before,after)
    return before['source_url']!=after['source_url']

_lock = threading.RLock()

def utcnow(): return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, path: str):
        self.path=path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db=sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=10)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS domain_cooldowns (host TEXT PRIMARY KEY, until_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS feeds (
           id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
           source_url TEXT NOT NULL,kind TEXT NOT NULL DEFAULT 'web',
           recipe TEXT NOT NULL DEFAULT '{}',interval_minutes INTEGER NOT NULL DEFAULT 720,
           enabled INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'new',
           last_run TEXT,last_success TEXT,next_run TEXT,created_at TEXT NOT NULL,
           last_error TEXT NOT NULL DEFAULT '',item_count INTEGER NOT NULL DEFAULT 0,
           consecutive_failures INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS recoveries (feed_id TEXT PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE, cycle INTEGER NOT NULL, failures INTEGER NOT NULL, not_before TEXT, expires_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS items (
           feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
           guid TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,
           summary TEXT NOT NULL DEFAULT '',published_at TEXT,first_seen_at TEXT NOT NULL,
           last_seen_at TEXT NOT NULL,PRIMARY KEY(feed_id,guid));
          CREATE TABLE IF NOT EXISTS runs (
           id INTEGER PRIMARY KEY AUTOINCREMENT, feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
           at TEXT NOT NULL, status TEXT NOT NULL, found INTEGER NOT NULL DEFAULT 0,
           inserted INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '', elapsed_ms INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS item_events (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
           guid TEXT NOT NULL, at TEXT NOT NULL, event_type TEXT NOT NULL,
           title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
          CREATE INDEX IF NOT EXISTS idx_item_events ON item_events(feed_id,id DESC);
          CREATE TABLE IF NOT EXISTS feed_revisions (
           feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
           revision INTEGER NOT NULL, changed_at TEXT NOT NULL,
           action TEXT NOT NULL, snapshot TEXT NOT NULL,
           PRIMARY KEY(feed_id,revision));
          CREATE INDEX IF NOT EXISTS idx_revisions ON feed_revisions(feed_id, revision DESC);
          CREATE INDEX IF NOT EXISTS idx_due ON feeds(enabled,next_run);
          CREATE INDEX IF NOT EXISTS idx_items_feed ON items(feed_id, first_seen_at DESC);
        ''')
        # Item lifecycle is observational. Missing jobs are not removed or
        # declared closed until two COMPLETE, successful inventory scans.
        item_columns={r[1] for r in self.db.execute('PRAGMA table_info(items)')}
        if 'missing_count' not in item_columns:
            self.db.execute('ALTER TABLE items ADD COLUMN missing_count INTEGER NOT NULL DEFAULT 0')
        if 'availability' not in item_columns:
            self.db.execute("ALTER TABLE items ADD COLUMN availability TEXT NOT NULL DEFAULT 'observed'")
        # Safe additive schema migration for existing 0.1 database files.
        if 'consecutive_failures' not in {r[1] for r in self.db.execute('PRAGMA table_info(feeds)')}:
            self.db.execute('ALTER TABLE feeds ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0')
        if 'schedule_phase_seconds' not in {r[1] for r in self.db.execute('PRAGMA table_info(feeds)')}:
            self.db.execute('ALTER TABLE feeds ADD COLUMN schedule_phase_seconds INTEGER')
        # Upgrade v0.1-v0.3 safely without changing any existing feed IDs.
        with _lock:
            if self.db.execute('SELECT 1 FROM feeds LIMIT 1').fetchone():
                self.db.execute('''INSERT OR IGNORE INTO feed_revisions
                (feed_id,revision,changed_at,action,snapshot)
                SELECT id,1,?, 'migrated',json_object(
                  'title',title,'description',description,'source_url',source_url,
                  'kind',kind,'recipe',json(recipe),'interval_minutes',interval_minutes,
                  'enabled',json(CASE WHEN enabled=1 THEN 'true' ELSE 'false' END))
                FROM feeds WHERE id NOT IN (SELECT feed_id FROM feed_revisions)''', (utcnow(),))

    @staticmethod
    def snapshot(row):
        return {key:row[key] for key in ('title','description','source_url','kind','recipe','interval_minutes','enabled')}

    def _record_revision(self, ident, action):
        row=self.public(dict(self.db.execute('SELECT * FROM feeds WHERE id=?',(ident,)).fetchone()))
        index=self.db.execute('SELECT COALESCE(MAX(revision),0)+1 FROM feed_revisions WHERE feed_id=?',(ident,)).fetchone()[0]
        self.db.execute('INSERT INTO feed_revisions (feed_id,revision,changed_at,action,snapshot) VALUES (?,?,?,?,?)',
                        (ident,index,utcnow(),action,json.dumps(self.snapshot(row),ensure_ascii=False)))
        # Maintain at most 40 recent revisions per feed.
        self.db.execute('DELETE FROM feed_revisions WHERE feed_id=? AND revision NOT IN '
                        '(SELECT revision FROM feed_revisions WHERE feed_id=? ORDER BY revision DESC LIMIT 40)',
                        (ident,ident))

    def revisions(self, ident):
        return self.fetchall('SELECT revision,changed_at,action,snapshot FROM feed_revisions WHERE feed_id=? ORDER BY revision DESC LIMIT 40',(ident,))

    def restore_revision(self, ident, revision):
        previous=self.get(ident)
        if previous is None: raise ValueError('Feed does not exist')
        found=self.fetchone('SELECT snapshot FROM feed_revisions WHERE feed_id=? AND revision=?',(ident,revision))
        if not found: raise ValueError('Revision does not exist')
        data=json.loads(found['snapshot'])
        if previous['item_count'] and source_identity_changed(previous,data):
            raise ValueError('Cannot restore a different source URL after storing articles')
        return self.update(ident, data, action='restored')

    def close(self): self.db.close()
    def fetchone(self,sql,params=()):
        with _lock:
            row=self.db.execute(sql,params).fetchone()
            return dict(row) if row else None
    def fetchall(self,sql,params=()):
        with _lock:
            return [dict(r) for r in self.db.execute(sql,params).fetchall()]
    def public(self,row):
        if row is None: return None
        row=dict(row)
        row['recipe']=json.loads(row['recipe'])
        row['enabled']=bool(row['enabled'])
        return row
    def create(self,data):
        ident=data.get('id') or secrets.token_hex(14)
        if not isinstance(ident, str) or len(ident)!=28 or any(c not in '0123456789abcdef' for c in ident):
            raise ValueError('Invalid feed ID')
        now=utcnow()
        with _lock:
            self.db.execute('''INSERT INTO feeds (id,title,description,source_url,kind,recipe,interval_minutes,created_at,next_run)
            VALUES (?,?,?,?,?,?,?,?,?)''', (ident,data['title'],data.get('description',''),data['source_url'],data.get('kind','web'),json.dumps(data.get('recipe') or {}),data.get('interval_minutes',720),now,now))
            if data.get('enabled') is False:
                self.db.execute('UPDATE feeds SET enabled=0 WHERE id=?',(ident,))
            self._ensure_phase(ident)
            self._record_revision(ident,'created')
        return self.get(ident)
    def get(self,ident):
        return self.public(self.fetchone('''SELECT feeds.*,
            (SELECT MAX(revision) FROM feed_revisions WHERE feed_id=feeds.id) AS recipe_revision
            FROM feeds WHERE feeds.id=?''',(ident,)))
    def list(self): return [self.public(r) for r in self.fetchall('SELECT * FROM feeds ORDER BY created_at DESC')]
    def update(self,ident,data,*,action='updated'):
        keys=['title','description','source_url','kind','interval_minutes','enabled','recipe']
        sets=[]; params=[]
        for k in keys:
            if k in data:
                sets.append(k+'=?')
                params.append(json.dumps(data[k]) if k=='recipe' else int(data[k]) if k=='enabled' else data[k])
        if not sets: return self.get(ident)
        sets.append('next_run=?');params.append(utcnow())
        params.append(ident)
        with _lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                self.db.execute('UPDATE feeds SET '+','.join(sets)+' WHERE id=?',params)
                self._ensure_phase(ident)
                self.db.execute('DELETE FROM recoveries WHERE feed_id=?',(ident,))
                self._record_revision(ident,action)
                self.db.execute('COMMIT')
            except Exception:
                self.db.execute('ROLLBACK')
                raise
        return self.get(ident)
    def create_many(self, rows: list[dict]) -> tuple[int, int]:
        """Import atomically: no partially imported bundle on SQLite errors."""
        inserted = 0
        with _lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                seen = {(r['source_url'], r['title']) for r in self.db.execute('SELECT source_url,title FROM feeds')}
                ids = {r[0] for r in self.db.execute('SELECT id FROM feeds')}
                for data in rows:
                    key = (data['source_url'], data['title'])
                    ident = data.get('id') or secrets.token_hex(14)
                    if key in seen or ident in ids:
                        continue
                    if len(ident)!=28 or any(c not in '0123456789abcdef' for c in ident):
                        raise ValueError('Invalid imported feed ID')
                    now=utcnow()
                    self.db.execute('''INSERT INTO feeds
                        (id,title,description,source_url,kind,recipe,interval_minutes,enabled,created_at,next_run)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''',
                        (ident,data['title'],data.get('description',''),data['source_url'],
                         data.get('kind','web'),json.dumps(data.get('recipe') or {}),
                         data.get('interval_minutes',720),int(data.get('enabled',True)),now,now))
                    self._ensure_phase(ident)
                    self._record_revision(ident,'imported')
                    inserted += 1
                    seen.add(key)
                    ids.add(ident)
                self.db.execute('COMMIT')
            except Exception:
                self.db.execute('ROLLBACK')
                raise
        return inserted, len(rows)-inserted

    def _ensure_phase(self,ident):
        row=self.db.execute('SELECT interval_minutes,schedule_phase_seconds FROM feeds WHERE id=?',(ident,)).fetchone()
        if row['interval_minutes']!=720:
            self.db.execute('UPDATE feeds SET schedule_phase_seconds=NULL WHERE id=?',(ident,));return
        phase=row['schedule_phase_seconds']
        if phase is None:
            phases=sorted(r[0] for r in self.db.execute('SELECT schedule_phase_seconds FROM feeds WHERE interval_minutes=720 AND schedule_phase_seconds IS NOT NULL AND id!=?',(ident,)))
            if not phases:phase=0
            else:
                pairs=list(zip(phases,phases[1:]+[phases[0]+43200]))
                start,end=max(pairs,key=lambda p:p[1]-p[0]);phase=(start+(end-start)//2)%43200
        self.db.execute('UPDATE feeds SET schedule_phase_seconds=?,next_run=? WHERE id=?',(phase,next_phase(phase,720).isoformat(),ident))

    def spread_schedule(self,now=None):
        now=now or datetime.now(timezone.utc)
        with _lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                feeds=[self.public(r) for r in self.db.execute('SELECT * FROM feeds WHERE enabled=1')]
                phases=spread_phases(feeds)
                for f in feeds:
                    phase=phases[f['id']]
                    self.db.execute('UPDATE feeds SET interval_minutes=720,schedule_phase_seconds=?,next_run=? WHERE id=?',(phase,next_phase(phase,720,now).isoformat(),f['id']))
                    self._record_revision(f['id'],'12h staggered schedule')
                self.db.execute('COMMIT')
            except Exception:
                self.db.execute('ROLLBACK');raise
        return {'updated':len(feeds),'interval_minutes':720,'timezone':'Asia/Shanghai','daytime_slot':'08:00–20:00','phases':phases}

    def backup_to(self, path: str):
        """Consistent online snapshot even while SQLite WAL is active."""
        with _lock:
            target = sqlite3.connect(path)
            try:
                self.db.backup(target)
            finally:
                target.close()

    def delete(self,ident):
        with _lock: self.db.execute('DELETE FROM feeds WHERE id=?',(ident,))
    def defer(self,ident,seconds):
        # Domain-level throttling should not starve later feeds on the same site.
        next_run=(datetime.now(timezone.utc)+timedelta(seconds=max(1,int(seconds)))).isoformat()
        with _lock:
            self.db.execute('UPDATE feeds SET next_run=? WHERE id=?',(next_run,ident))
            self.db.execute('UPDATE recoveries SET not_before=MAX(not_before,?) WHERE feed_id=? AND not_before IS NOT NULL',(next_run,ident))

    def cool_domain(self, host, seconds):
        host=host.lower().rstrip('.')
        if not host:return
        until=(datetime.now(timezone.utc)+timedelta(seconds=min(604800,max(1,int(seconds))))).isoformat()
        with _lock:
            self.db.execute('DELETE FROM domain_cooldowns WHERE until_at<=?',(utcnow(),))
            self.db.execute('INSERT INTO domain_cooldowns(host,until_at) VALUES (?,?) ON CONFLICT(host) DO UPDATE SET until_at=MAX(until_at,excluded.until_at)',(host,until))

    def domain_delay(self, host):
        row=self.db.execute('SELECT until_at FROM domain_cooldowns WHERE host=?',(host.lower().rstrip('.'),)).fetchone()
        if not row:return 0
        import math
        return max(0,math.ceil((datetime.fromisoformat(row['until_at'])-datetime.now(timezone.utc)).total_seconds()))

    def cooldowns(self):
        return self.fetchall('SELECT host,until_at FROM domain_cooldowns WHERE until_at>? ORDER BY until_at',(utcnow(),))

    def due(self,limit=15):
        return [self.public(r) for r in self.fetchall('SELECT f.* FROM feeds f LEFT JOIN recoveries r ON r.feed_id=f.id WHERE f.enabled=1 AND (f.next_run<=? OR (r.not_before<=? AND r.expires_at>?)) ORDER BY f.next_run LIMIT ?', (utcnow(),utcnow(),utcnow(),limit))]
    def update_recovery(self,feed,error):
        # Called in finish's transaction: a failure and its recovery are atomic.
        recipe=feed.get('recipe') or {}
        transient=any(x in str(error) for x in (
            'Upstream connection failed: timeout','Upstream connection failed: dns_resolution',
            'Upstream connection failed: connection_closed','Upstream connection failed: connection_refused',
            'Upstream connection failed: network_unreachable','Upstream connection failed: egress_timeout',
            'Upstream connection failed: egress_connection','Upstream HTTP 408','Upstream HTTP 500',
            'Upstream HTTP 502','Upstream HTTP 503','Upstream HTTP 504'))
        if error is None or not transient or recipe.get('request_method','GET')!='GET':
            self.db.execute('DELETE FROM recoveries WHERE feed_id=?',(feed['id'],));return
        import random
        period=feed['interval_minutes']*60;phase=feed.get('schedule_phase_seconds') or 0
        stamp=datetime.now(timezone.utc).timestamp();cycle=int((stamp-phase)//period)
        expires=datetime.fromtimestamp((cycle+1)*period+phase,timezone.utc).isoformat()
        prior=self.db.execute('SELECT * FROM recoveries WHERE feed_id=?',(feed['id'],)).fetchone()
        count=prior['failures']+1 if prior and prior['cycle']==cycle else 1
        delay=random.randint(300,900) if count==1 else random.randint(1800,3600)
        when=(datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat() if count<=2 else None
        self.db.execute('INSERT INTO recoveries VALUES (?,?,?,?,?) ON CONFLICT(feed_id) DO UPDATE SET cycle=excluded.cycle,failures=excluded.failures,not_before=excluded.not_before,expires_at=excluded.expires_at',(feed['id'],cycle,count,when,expires))

    def recoveries(self):
        return self.fetchall('SELECT * FROM recoveries WHERE not_before IS NOT NULL AND expires_at>? ORDER BY not_before',(utcnow(),))

    def entries(self,ident,limit=100):
        return self.fetchall('''SELECT * FROM items WHERE feed_id=? ORDER BY COALESCE(published_at,first_seen_at) DESC,first_seen_at DESC LIMIT ?''',(ident,limit))
    def monitor(self):
        """Source-level stale/error diagnosis without changing source status."""
        from datetime import datetime,timezone
        now=datetime.now(timezone.utc)
        rows=[]
        for feed in self.list():
            if not feed['enabled']:
                state='paused'
            elif feed['status']=='error':
                state='error'
            elif not feed.get('last_success'):
                state='never_succeeded'
            else:
                age=(now-datetime.fromisoformat(feed['last_success']).astimezone(timezone.utc)).total_seconds()/60
                state='stale' if age>max(360,3*feed['interval_minutes']) else 'healthy'
            rows.append({'id':feed['id'],'title':feed['title'],'state':state,
                'last_success':feed.get('last_success'),'last_error':feed.get('last_error'),
                'next_run':feed.get('next_run'),'item_count':feed['item_count']})
        counts={status:sum(x['state']==status for x in rows) for status in
            ('healthy','stale','error','never_succeeded','paused')}
        return {'total':len(rows),'counts':counts,'sources':rows}

    def item_events(self,ident,limit=100):
        return self.fetchall('SELECT id,feed_id,guid,at,event_type,title,detail FROM item_events WHERE feed_id=? ORDER BY id DESC LIMIT ?', (ident,min(200,max(1,int(limit)))))

    def item_lifecycle(self, ident, limit=200):
        return self.fetchall('SELECT guid,title,url,availability,missing_count,first_seen_at,last_seen_at FROM items WHERE feed_id=? ORDER BY last_seen_at DESC LIMIT ?', (ident,limit))

    def runs(self,ident=None,limit=40):
        if ident:
            return self.fetchall('SELECT * FROM runs WHERE feed_id=? ORDER BY id DESC LIMIT ?', (ident,limit))
        return self.fetchall('SELECT * FROM runs ORDER BY id DESC LIMIT ?', (limit,))
    def finish(self,feed,entries,error,elapsed_ms,success_message=""):
        now=utcnow(); success=error is None
        interval=feed['interval_minutes']
        failures=(feed.get('consecutive_failures') or 0)+1 if not success else 0
        if not success and feed.get('schedule_phase_seconds') is None:
            # Consecutive (not lifetime) errors; retry progressively, and reset on recovery.
            interval=min(1440, max(5, 5*(2**min(failures-1, 8))))
        next_run=(next_phase(feed['schedule_phase_seconds'],interval) if feed.get('schedule_phase_seconds') is not None else datetime.now(timezone.utc)+timedelta(minutes=interval)).isoformat()
        with _lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                # A rule or URL edited during an in-flight request invalidates
                # that result. Never commit articles produced by an old recipe.
                expected=feed.get('recipe_revision')
                if expected is not None:
                    current=self.db.execute('SELECT MAX(revision) FROM feed_revisions WHERE feed_id=?',(feed['id'],)).fetchone()[0]
                    if current!=expected:
                        self.db.execute('ROLLBACK')
                        return {'status':'stale','found':0,'inserted':0,
                                'message':'Recipe changed while fetching; outdated results were discarded'}
                added=0
                if success:
                    for x in entries:
                        guid=guid_for(x['url'])
                        old=self.db.execute('SELECT guid,title,summary,availability FROM items WHERE feed_id=? AND guid=?',(feed['id'],guid)).fetchone()
                        if old:
                            summary=x.get('summary') or ''
                            changed=(old['title']!=x['title'] or old['summary']!=summary)
                            reappeared=(old['availability']!='observed')
                            self.db.execute("UPDATE items SET title=?,summary=?,published_at=COALESCE(?,published_at),last_seen_at=?,missing_count=0,availability='observed' WHERE feed_id=? AND guid=?",(x['title'],summary,x.get('published_at'),now,feed['id'],guid))
                            if reappeared or changed:
                                self.db.execute('INSERT INTO item_events(feed_id,guid,at,event_type,title,detail) VALUES (?,?,?,?,?,?)',
                                    (feed['id'],guid,now,'reappeared' if reappeared else 'updated',x['title'],
                                     'Observed again' if reappeared else 'Title or summary changed'))
                        else:
                            self.db.execute('INSERT INTO items (feed_id,guid,title,url,summary,published_at,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?,?,?)',(feed['id'],guid,x['title'],x['url'],x.get('summary') or '',x.get('published_at'),now,now))
                            self.db.execute('INSERT INTO item_events(feed_id,guid,at,event_type,title,detail) VALUES (?,?,?,?,?,?)',
                                (feed['id'],guid,now,'new',x['title'],'First observed'))
                            added+=1
                    # An inventory can mark disappearing job ads only when the
                    # Recipe explicitly declares a complete snapshot. Never
                    # guess closures from ordinary paginated news lists.
                    recipe=feed.get('recipe') or {}
                    if recipe.get('content_type') == 'jobs' and recipe.get('complete_inventory') is True:
                        observed=[guid_for(x['url']) for x in entries]
                        if observed:
                            placeholders=','.join('?' for _ in observed)
                            absent=self.db.execute(f"SELECT guid,title,missing_count FROM items WHERE feed_id=? AND guid NOT IN ({placeholders})",[feed['id'],*observed]).fetchall()
                            for prior in absent:
                                new_count=prior['missing_count']+1
                                status='possibly_closed' if new_count>=2 else 'missing_once'
                                self.db.execute('UPDATE items SET missing_count=?,availability=? WHERE feed_id=? AND guid=?',
                                                (new_count,status,feed['id'],prior['guid']))
                                if new_count in (1,2):
                                    self.db.execute('INSERT INTO item_events(feed_id,guid,at,event_type,title,detail) VALUES (?,?,?,?,?,?)',
                                        (feed['id'],prior['guid'],now,status,prior['title'],f'Absent in {new_count} complete inventories'))
                    self.db.execute('''UPDATE feeds SET status='healthy',last_run=?,last_success=?,last_error='',next_run=?,consecutive_failures=0,item_count=(SELECT COUNT(*) FROM items WHERE feed_id=?) WHERE id=?''',(now,now,next_run,feed['id'],feed['id']))
                else:
                    self.db.execute('''UPDATE feeds SET status='error',last_run=?,last_error=?,next_run=?,consecutive_failures=? WHERE id=?''',(now,str(error)[:400],next_run,failures,feed['id']))
                self.update_recovery(feed,error)
                self.db.execute('INSERT INTO runs (feed_id,at,status,found,inserted,message,elapsed_ms) VALUES (?,?,?,?,?,?,?)',(feed['id'],now,'success' if success else 'error',len(entries),added,success_message[:400] if success else str(error)[:400],elapsed_ms))
                # Bound activity/event history independently from actual items.
                self.db.execute('DELETE FROM item_events WHERE id IN (SELECT id FROM item_events WHERE feed_id=? ORDER BY id DESC LIMIT -1 OFFSET 1000)',(feed['id'],))
                # Keep history compact without dropping feed items.
                self.db.execute('DELETE FROM runs WHERE id IN (SELECT id FROM runs WHERE feed_id=? ORDER BY id DESC LIMIT -1 OFFSET 100)',(feed['id'],))
                self.db.execute('COMMIT')
            except Exception:
                self.db.execute('ROLLBACK')
                raise
        return {'status':'success' if success else 'error','found':len(entries),'inserted':added,'message':str(error) if error else success_message}
    def stats(self):
        return self.fetchone('SELECT COUNT(*) AS feeds,COALESCE(SUM(item_count),0) AS items,SUM(CASE WHEN status="healthy" THEN 1 ELSE 0 END) AS healthy,SUM(CASE WHEN status="error" THEN 1 ELSE 0 END) AS errors,COALESCE(SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END),0) AS active_feeds,COALESCE(SUM(CASE WHEN enabled=1 AND status="healthy" THEN 1 ELSE 0 END),0) AS active_healthy,COALESCE(SUM(CASE WHEN enabled=1 AND status="error" THEN 1 ELSE 0 END),0) AS active_errors,COALESCE(SUM(CASE WHEN enabled=0 THEN 1 ELSE 0 END),0) AS paused FROM feeds')
