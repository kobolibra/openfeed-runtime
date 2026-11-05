"""Offline SQLite/RSS baseline only; deliberately not a browser/network benchmark.

Usage: python tools/benchmark_local.py --feeds 300 --cycles 3
"""
from __future__ import annotations
import argparse
import json
import resource
import statistics
import sys
import tempfile
import time
from pathlib import Path
from openfeed.storage import Store
from openfeed.extract import render_rss


def benchmark(feeds=300, cycles=3):
    if not 1 <= feeds <= 500 or not 1 <= cycles <= 10:
        raise ValueError('Use at most 500 feeds / 10 cycles')
    durations=[]
    with tempfile.TemporaryDirectory(prefix='openfeed-benchmark-') as directory:
        db=Store(str(Path(directory)/'benchmark.sqlite3'))
        started=time.perf_counter()
        feed_ids=[]
        for i in range(feeds):
            created=db.create({'title':f'Financial research {i:03d}',
                'source_url':f'https://research-{i:03d}.example.org/insights',
                'recipe':{'mode':'css','item_selector':'article'},'interval_minutes':60})
            feed_ids.append(created['id'])
        for cycle in range(cycles):
            for i,ident in enumerate(feed_ids):
                records=[{'title':f'Report {j}',
                    'url':f'https://research-{i:03d}.example.org/reports/{j}',
                    'published_at':'2026-10-20'} for j in range(5+cycle)]
                start=time.perf_counter()
                result=db.finish(db.get(ident),records,None,4)
                assert result['status']=='success'
                durations.append((time.perf_counter()-start)*1000)
        document_count=sum(len(db.entries(ident)) for ident in feed_ids)
        for ident in feed_ids[:10]:
            info=db.get(ident)
            xml=render_rss(info,db.entries(ident),f'https://feeds.example.org/rss/{ident}.xml')
            assert b'<rss version="2.0"' in xml
        results={'feeds':feeds,'cycles':cycles,'items':document_count,
            'refresh_operations':len(durations),'elapsed_seconds':round(time.perf_counter()-started,3),
            'mean_refresh_ms':round(statistics.mean(durations),3),
            'p95_refresh_ms':round(sorted(durations)[max(0,int(.95*len(durations))-1)],3),
            'peak_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),2),
            'scope':'SQLite/storage/RSS only; zero external requests and no Chromium'}
        db.close()
        return results


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--feeds',type=int,default=300)
    parser.add_argument('--cycles',type=int,default=3)
    args=parser.parse_args()
    print(json.dumps(benchmark(args.feeds,args.cycles),indent=2))
