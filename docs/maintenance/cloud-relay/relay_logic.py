import hashlib,hmac,json,time
EXPIRY=1794053385
REPO='kobolibra/openfeed-feeds'
def signature(key,root,generation,not_before):
 payload=json.dumps([REPO,str(root),int(generation),int(not_before),EXPIRY],separators=(',',':'))
 return hmac.new(key.encode(),payload.encode(),hashlib.sha256).hexdigest()
def authorize(actor,owner,key,inputs,run_id,now):
 if now>=EXPIRY:return None
 if actor==owner and not inputs.get('signature'):return {'root':str(run_id),'generation':0,'not_before':int(now)}
 if actor not in (owner,'github-actions[bot]'):raise ValueError('Actor not allowed')
 root=str(inputs['root']);generation=int(inputs['generation']);not_before=int(inputs['not_before'])
 if not root.isdigit() or generation<1 or not 0<not_before<EXPIRY:raise ValueError('Invalid relay bounds')
 if not hmac.compare_digest(signature(key,root,generation,not_before),inputs['signature']):raise ValueError('Invalid relay signature')
 if not_before>now+30:raise ValueError('Relay dispatched before its slot')
 return {'root':root,'generation':generation,'not_before':not_before}
def claim(cursor,root,generation,run_id,now,restart=False):
 if generation==0:
  if cursor and now-cursor['at']<1200 and not restart:return None
 elif not cursor or cursor['root']!=root or cursor['generation']!=generation-1:return None
 return {'root':root,'generation':generation,'run_id':str(run_id),'at':int(now)}
