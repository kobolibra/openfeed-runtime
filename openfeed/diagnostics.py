"""Explain current failures without changing or concealing source state."""
from datetime import datetime,timezone
from urllib.parse import urlsplit

def failure_summary(feeds,now=None):
 now=now or datetime.now(timezone.utc)
 groups={'transport':[],'access':[],'extraction':[],'browser':[],'other':[]};recent_domains=set()
 for f in feeds:
  if not f.get('enabled') or f.get('status')!='error':continue
  message=f.get('last_error') or ''
  if 'Upstream connection failed:' in message or 'net::ERR_CONNECTION' in message or 'net::ERR_NETWORK' in message or 'net::ERR_TUNNEL_CONNECTION_FAILED' in message:
   kind='transport'
  elif any(x in message for x in ('Upstream HTTP 401','Upstream HTTP 403','Upstream HTTP 429','Upstream HTTP 405','Source access barrier:','challenge','verification')):kind='access'
  elif any(x in message for x in ('BrowserType.launch','browser has been closed','Browser render timed out','Isolated browser worker timed out')):kind='browser'
  elif any(x in message for x in ('No valid items','Quality gate','selector','Locator.wait_for','JSON','contract')):kind='extraction'
  else:kind='other'
  groups[kind].append(f['id'])
  if kind=='transport':
   try:
    at=datetime.fromisoformat(f.get('last_run') or '')
    if at.tzinfo is None:at=at.replace(tzinfo=timezone.utc)
    if 0<=(now-at).total_seconds()<=3600:
     host=urlsplit((f.get('recipe') or {}).get('fetch_url') or f.get('source_url','')).hostname
     if host:recent_domains.add(host)
   except (ValueError,TypeError):pass
 return {'error_counts':{k:len(v) for k,v in groups.items()},'error_feed_ids':groups,
         'recent_transport_domains':len(recent_domains),'suspected_network_issue':len(recent_domains)>=3,
         'paused_count':sum(not f.get('enabled') for f in feeds),
         'history_preserved':True}
