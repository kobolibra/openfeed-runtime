"""Stable refresh phases and publication hours, independent of host timezone."""
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from urllib.parse import urlsplit

BEIJING=timezone(timedelta(hours=8),'Asia/Shanghai')
REFRESH_MINUTES=720

def _rank(value):return sha256(value.encode()).hexdigest()

def spread_phases(feeds,interval_minutes=REFRESH_MINUTES):
    """Even global slots, with each origin's feeds interleaved around the cycle."""
    groups=defaultdict(list)
    for feed in feeds:
        url=(feed.get('recipe') or {}).get('fetch_url') or feed['source_url']
        p=urlsplit(url);origin=(p.scheme,p.hostname,p.port)
        groups[origin].append(feed)
    ordered=[]
    for origin,group in groups.items():
        group.sort(key=lambda f:_rank(f['id']))
        # Different origins get different offsets, while each origin stays uniform.
        offset=int(_rank(str(origin))[:8],16)/2**32
        for i,f in enumerate(group):ordered.append(((i+offset)/len(group),_rank(f['id']),f['id']))
    ordered.sort();period=interval_minutes*60;n=len(ordered)
    if n>period:raise ValueError('Too many feeds for second-resolution refresh slots')
    return {f[2]:i*period//n for i,f in enumerate(ordered)} if n else {}

def next_phase(phase,interval_minutes,now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Scheduling requires an aware timestamp')
    period=interval_minutes*60
    if not 0<=phase<period:raise ValueError('Invalid refresh phase')
    # UTC midnight is 08:00 Beijing. A 12h period gives one daytime slot 08–20.
    stamp=now.timestamp();slot=(int((stamp-phase)//period)+1)*period+phase
    return datetime.fromtimestamp(slot,timezone.utc)

def publication_slot(now=None):
    now=(now or datetime.now(timezone.utc)).astimezone(BEIJING)
    # 08:00 through the 22:00 tick, including wake-up catch-up before 22:00.
    if 8<=now.hour<22 or (now.hour==22 and now.minute==0):return now.strftime('%Y-%m-%dT%H')
    return None

def claim_publication_slot(path,now=None):
    """Persist a once-per-hour attempt under the caller's exclusive cycle lock."""
    import json,os
    from pathlib import Path
    slot=publication_slot(now)
    if slot is None:return False
    path=Path(path)
    try:previous=json.loads(path.read_text())
    except FileNotFoundError:previous={}
    if previous.get('slot')==slot:return False
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps({'slot':slot,'timezone':'Asia/Shanghai'}))
    os.replace(temp,path)
    return True
