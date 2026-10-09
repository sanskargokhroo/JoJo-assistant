"""Optional Home Assistant bridge. Only explicitly allowlisted entities can act."""
import ipaddress
import json
import os
import re
from urllib.parse import urlsplit, quote

DOMAINS={'light','switch','fan','media_player'}

def config():
    url=os.environ.get('JOJO_HA_URL','').rstrip('/')
    token=os.environ.get('JOJO_HA_TOKEN','')
    allowed={v.strip() for v in os.environ.get('JOJO_HA_ENTITIES','').split(',') if v.strip()}
    if not url or not token or not allowed:raise ValueError('Smart-home setup pending: Home Assistant URL, token aur allowed device IDs configure kijiye.')
    p=urlsplit(url)
    local=p.hostname in {'localhost','127.0.0.1','::1'} or (p.hostname or '').endswith('.local')
    try:local=local or ipaddress.ip_address(p.hostname).is_private
    except ValueError:pass
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.query or p.fragment or (p.scheme=='http' and not local):
        raise ValueError('Use HTTPS or an explicitly configured local Home Assistant address; no credentials in URL.')
    return url,token,allowed

def request(method,path,data=None):
    import requests
    url,token,_=config()
    with requests.Session() as session:
        session.trust_env=False
        response=session.request(method,url+'/api/'+path,headers={'Authorization':'Bearer '+token},json=data,timeout=(4,8),allow_redirects=False)
        if response.status_code not in (200,201):raise RuntimeError('Home Assistant request failed (HTTP '+str(response.status_code)+'); no automatic retry.')
        return response.json()

def list_smart_devices() -> str:
    """List configured Home Assistant devices and their observed states. No network scan/pairing."""
    from jojo_capabilities import enabled
    if not enabled('smart_home'):return '⚠ Smart-home capability is disabled.'
    try:
        _,_,allowed=config()
        rows=request('GET','states')
        return json.dumps([{'id':r['entity_id'],'name':r.get('attributes',{}).get('friendly_name',r['entity_id']),'state':r.get('state')}
            for r in rows if r.get('entity_id') in allowed and r['entity_id'].split('.')[0] in DOMAINS],ensure_ascii=False)
    except Exception as exc:return '⚠ '+(str(exc) if isinstance(exc,ValueError) else 'Smart-home connection unavailable; device states not verified.')

def control_smart_device(entity_id: str, state: str) -> str:
    """Turn an explicitly allowlisted light/switch/fan/media player on or off when requested by the user."""
    from jojo_capabilities import enabled
    if not enabled('smart_home'):return '⚠ Smart-home capability is disabled.'
    try:
        _,_,allowed=config()
        if entity_id not in allowed or not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',entity_id):raise ValueError('Device is not on your smart-home allowlist.')
        domain=entity_id.split('.')[0]
        if domain not in DOMAINS or state not in {'on','off'}:raise ValueError('Only on/off for allowed lights, switches, fans and media players is supported.')
        current=request('GET','states/'+quote(entity_id,safe=''))
        if current.get('state') in {'unavailable','unknown'}:return '⚠ Device unavailable; no action sent.'
        if current.get('state')==state:return 'Device already '+state+'.'
        request('POST','services/'+domain+'/turn_'+state,{'entity_id':entity_id})
        observed=request('GET','states/'+quote(entity_id,safe='')).get('state')
        return 'Verified device state: '+state if observed==state else '⚠ Request sent; desired state not verified. No automatic repeat.'
    except Exception as exc:return '⚠ '+(str(exc) if isinstance(exc,ValueError) else 'Smart-home result uncertain/unavailable. No automatic retry; check the device.')

def smart_command(text):
    value=text.strip().casefold()
    if value in {'smart devices','smart devices list','smart devices dikhao','स्मार्ट डिवाइस दिखाओ'}:return list_smart_devices()
    match=re.fullmatch(r'smart\s+([a-z_]+\.[a-z0-9_]+)\s+(on|off)',value)
    return control_smart_device(*match.groups()) if match else None
