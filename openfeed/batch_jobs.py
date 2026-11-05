"""Durable, single-process batch refresh work queue.

The DB tracks intent and per-feed progress. A crash changes running jobs to
interrupted on restart; administrators may resume explicitly. No hidden retries.
"""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class BatchJobs:
    def __init__(self, path):
        self.db=sqlite3.connect(path, check_same_thread=False, timeout=10, isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.lock=threading.RLock()
        with self.lock:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('''CREATE TABLE IF NOT EXISTS batch_jobs (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, feed_ids TEXT NOT NULL, results TEXT NOT NULL,
                next_index INTEGER NOT NULL DEFAULT 0)''')
            self.db.execute("UPDATE batch_jobs SET status='interrupted', updated_at=? WHERE status='running'",(now(),))

    def close(self):
        with self.lock: self.db.close()

    def create(self, ids):
        with self.lock:
            # Limit retained history without removing incomplete jobs.
            count=self.db.execute("SELECT count(*) FROM batch_jobs WHERE status IN ('pending','running')").fetchone()[0]
            if count>=5: raise ValueError('Too many active batches')
            ident=uuid.uuid4().hex
            t=now()
            self.db.execute('INSERT INTO batch_jobs VALUES (?,?,?,?,?,?,?)',
                            (ident,'pending',t,t,json.dumps(ids),json.dumps([]),0))
            return self.get(ident)

    def get(self, ident):
        with self.lock:
            r=self.db.execute('SELECT * FROM batch_jobs WHERE id=?',(ident,)).fetchone()
            if not r:return None
            d=dict(r)
            d['feed_ids']=json.loads(d['feed_ids'])
            d['results']=json.loads(d['results'])
            d['total']=len(d['feed_ids'])
            d['completed']=d['next_index']
            return d

    def claim(self, ident):
        with self.lock:
            r=self.get(ident)
            if not r or r['status']!='pending':return False
            return bool(self.db.execute("UPDATE batch_jobs SET status='running',updated_at=? WHERE id=? AND status='pending'",(now(),ident)).rowcount)

    def finish_one(self,ident,feed_id,outcome):
        with self.lock:
            r=self.get(ident)
            if not r or r['status']!='running':return False
            if r['next_index']>=r['total'] or r['feed_ids'][r['next_index']]!=feed_id:return False
            results=r['results']+[outcome]
            n=r['next_index']+1
            new_status='completed' if n==r['total'] else 'running'
            self.db.execute('UPDATE batch_jobs SET results=?,next_index=?,status=?,updated_at=? WHERE id=?',
                            (json.dumps(results),n,new_status,now(),ident))
            return True

    def yield_pending(self, ident):
        """Cooperatively requeue unfinished jobs for fair scheduling."""
        with self.lock:
            return bool(self.db.execute(
                "UPDATE batch_jobs SET status='pending',updated_at=? "
                "WHERE id=? AND status='running'", (now(), ident)).rowcount)

    def interrupt(self, ident):
        """Persist a stopped run immediately, so it can resume without a restart."""
        with self.lock:
            return bool(self.db.execute(
                "UPDATE batch_jobs SET status='interrupted',updated_at=? "
                "WHERE id=? AND status='running'", (now(), ident)).rowcount)

    def cancel(self, ident):
        """Persist cancellation; an in-flight fetch may finish but cannot commit batch progress."""
        with self.lock:
            return bool(self.db.execute(
                "UPDATE batch_jobs SET status='cancelled',updated_at=? "
                "WHERE id=? AND status IN ('pending','running','interrupted')",
                (now(), ident)).rowcount)

    def resume(self,ident):
        with self.lock:
            r=self.get(ident)
            if not r or r['status']!='interrupted':return False
            self.db.execute("UPDATE batch_jobs SET status='pending',updated_at=? WHERE id=?",(now(),ident))
            return True

    def pending(self):
        with self.lock:
            return [r[0] for r in self.db.execute("SELECT id FROM batch_jobs WHERE status='pending' ORDER BY created_at LIMIT 5")]
