import datetime

def release_time(environment,parent,now):
    rules=environment.get('protection_rules',[])
    if not any(x.get('type')=='wait_timer' and x.get('wait_timer',0)>=10 for x in rules):
        raise ValueError('Required ten-minute platform timer is missing; refusing recursive dispatch')
    created=datetime.datetime.fromisoformat(parent['created_at'].replace('Z','+00:00'))
    if created.tzinfo is None:raise ValueError('Parent timestamp requires timezone')
    earliest=int(created.timestamp())+600
    if now<earliest:raise ValueError('Platform timer released early; no self-dispatch')
    return max(earliest,int(now))

def reserve(git,claim,root,generation,run_id,now,restart=False):
    import json,subprocess
    from pathlib import Path
    p=Path('relay-cursor.json')
    for attempt in range(3):
        old=json.loads(p.read_text()) if p.exists() else None
        new=claim(old,root,generation,run_id,now,restart)
        if new is None:return False
        expected=git('rev-parse','HEAD');p.write_text(json.dumps(new,indent=2));git('config','user.name','OpenFeed Clock');git('config','user.email','openfeed@users.noreply.github.com');git('add','--','relay-cursor.json');git('commit','-m','Reserve scheduled publication tick '+str(run_id));commit=git('rev-parse','HEAD')
        try:git('push','origin','HEAD:shadow-state');return True
        except subprocess.CalledProcessError:
            remote=git('ls-remote','origin','refs/heads/shadow-state').split()[0]
            if remote==commit:return True
            # Only this job's private metadata checkout is reset. Never replace
            # the remote DB or roll back an acknowledged management edit.
            if attempt==2:raise
            git('fetch','origin','shadow-state');git('reset','--hard','origin/shadow-state')
    return False
