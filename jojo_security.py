"""Local defensive checks, passive link inspection and an in-app security watcher."""
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import urlsplit, unquote
from jojo_config import ROOT, DATA_DIR, read_preferences

LIMITATION = 'This is a risk check, not proof that a device, link or file is safe or hacked.'
_lock=threading.RLock()
_audit_lock=threading.Lock()
_status={'status':'not_checked','checked_at':None,'findings':[],'unknown':[],'alert_id':'','summary':'Security has not been checked yet.'}
_worker=None
_scan={'status':'idle','message':'No scan requested through JoJo.'}

def inspect_link(url: str, expected_domain: str = '') -> dict:
    """Inspect a URL locally without opening it, resolving it, or uploading it."""
    findings=[]
    def add(level,message):findings.append({'level':level,'message':message})
    value=url.strip()
    if len(value)>12000:return {'risk':'high','host':'','findings':[{'level':'high','message':'URL is unusually long.'}],'limitation':LIMITATION}
    try:
        parsed=urlsplit(value if '://' in value or value.lower().startswith(('javascript:','data:','file:')) else 'https://'+value)
        host=(parsed.hostname or '').rstrip('.').lower()
        port=parsed.port
    except ValueError:
        return {'risk':'high','host':'','findings':[{'level':'high','message':'Malformed URL or port.'}],'limitation':LIMITATION}
    if parsed.scheme not in ('http','https') or not host:add('high','Unsupported/active URL scheme; do not open through JoJo.')
    if parsed.username is not None or parsed.password is not None:add('high','The URL contains user-info before @; the actual destination may be disguised.')
    if parsed.scheme=='http':add('review','Unencrypted HTTP; do not enter passwords or other private information.')
    if any(ord(c)>127 for c in host) or 'xn--' in host:add('review','Internationalized domain: inspect the exact spelling for lookalike characters.')
    try:
        ipaddress.ip_address(host)
        add('review','The destination is a numeric IP address; verify it is the intended device/site.')
    except ValueError:pass
    if host in {'bit.ly','tinyurl.com','t.co','is.gd','cutt.ly','shorturl.at'}:add('review','Shortened URL hides the final destination. Redirects were not followed.')
    if re.search(r'\.(exe|msi|scr|bat|cmd|ps1|vbs|js|apk|iso)$',unquote(parsed.path).lower()):
        add('review','Link appears to download an executable/script or installer. Check the source and file before running it.')
    if expected_domain:
        expected=urlsplit('https://'+expected_domain.strip().lower()).hostname
        if not expected or (host != expected and not host.endswith('.'+expected)):
            add('high','Destination does not match the expected domain.')
    if port and port not in (80,443):add('review','Nonstandard port; verify why this service uses it.')
    from jojo_policy import blocked_reason
    if blocked_reason(host):add('high','This destination is on JoJo’s restricted-app/site list.')
    risk='high' if any(f['level']=='high' for f in findings) else 'review' if findings else 'unknown'
    return {'risk':risk,'host':host,'findings':findings,'network_contacted':False,
            'summary':'No obvious URL-format warning found; reputation and page contents are unverified.' if not findings else 'Review the listed indicators before opening.', 'limitation':LIMITATION}

def probe(mode='audit', path=None, timeout=35):
    if os.name!='nt':return {'platform':{'available':False,'error':'Windows checks require Windows.'}}
    shell=Path(os.environ.get('SYSTEMROOT','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    env=dict(os.environ)
    if path is not None:env['JOJO_INSPECT_FILE']=str(path)
    result=subprocess.run([str(shell),'-NoProfile','-NonInteractive','-File',str(ROOT/'jojo_security_probe.ps1'),'-Mode',mode],
        capture_output=True,timeout=timeout,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Windows security probe unavailable (permission, policy or service error).')
    return json.loads(result.stdout.decode('utf-8-sig').strip())

def assess(raw):
    findings=[];unknown=[]
    def rows(section):
        value=raw.get(section,{})
        if not value.get('available'):
            unknown.append(section);return []
        data=value.get('data') or []
        return data if isinstance(data,list) else [data]
    def add(key,level,message,action):findings.append({'id':key,'level':level,'message':message,'action':action})
    av=rows('antivirus')
    for row in rows('defender'):
        passive=str(row.get('AMRunningMode','')).lower()=='passive'
        if row.get('RealTimeProtectionEnabled') is False:
            add('realtime','review' if passive else 'high','Defender real-time protection is not enabled.'+(' Another antivirus may be responsible.' if av else ''),'Check Windows Security → Virus & threat protection. Verify your active antivirus provider before changing settings.')
        if isinstance(row.get('AntivirusSignatureAge'),(int,float)) and row['AntivirusSignatureAge']>3:
            add('definitions','review','Defender definitions are more than three days old.','Update protection definitions in Windows Security.')
        if row.get('IsTamperProtected') is False:add('tamper','review','Defender tamper protection is off.','Review tamper protection in Windows Security.')
    for row in rows('threats'):
        if row.get('IsActive') is True:
            add('threat:'+str(row.get('ThreatID')),'critical','Defender reports an active threat: '+str(row.get('ThreatName','unknown')),
                'Open Windows Security → Protection history. Follow Defender remediation. Avoid sensitive sign-ins; disconnect the network if compromise is suspected.')
    for row in rows('firewall'):
        if row.get('Enabled') is False or row.get('Enabled')==0:
            add('firewall:'+str(row.get('Name')),'high','Firewall is disabled for profile '+str(row.get('Name'))+'.','Review Windows Security → Firewall & network protection; check any managed/third-party firewall before enabling.')
    for row in rows('startup'):
        if row.get('Encoded') or row.get('TempPath') or row.get('Bypass'):
            add('startup:'+str(row.get('Name')),'review','Startup entry needs review: '+str(row.get('Name'))+'. Encoded commands, temporary paths or bypass flags can also be legitimate.',
                'Check publisher and install source in Startup Apps. Do not delete it based only on this heuristic.')
    for row in rows('processes'):
        add('process:'+str(row.get('ProcessId')),'review','Encoded PowerShell command observed in '+str(row.get('Name'))+'. This alone is not evidence of malware.',
            'Check the owning application and publisher; investigate before stopping the process.')
    wifi=rows('wifi')
    if not wifi:unknown.append('wifi_authentication')
    elif any(re.search(r':\s*(open|wep)\s*$',str(line),re.I) for line in wifi):
        add('wifi_weak','high','Wi-Fi reports open or WEP authentication.','On your own router, use WPA3-Personal or WPA2-AES, a unique passphrase, current firmware and disable WPS. Avoid sensitive traffic until secured.')
    return {'status':'checked','checked_at':time.time(),'findings':findings,'unknown':list(dict.fromkeys(unknown)),
        'summary':f'{len(findings)} item(s) need review; {len(set(unknown))} checks unavailable. '+LIMITATION}

def security_snapshot():
    with _lock:return copy.deepcopy(_status)|{'defender_scan':copy.deepcopy(_scan)}

def start_defender_scan():
    """An explicit user action starts Defender's existing QuickScan policy."""
    with _lock:
        if _scan['status']=='running':return dict(_scan)
        _scan.update(status='running',message='Defender quick scan requested. Completion and findings are not yet known.')
    def run():
        try:
            probe('quick_scan',timeout=600)
            result={'status':'command_completed','message':'Defender scan command completed. Check Protection history and the refreshed report; completion does not prove the device is clean.'}
        except subprocess.TimeoutExpired:
            result={'status':'unknown','message':'Waiting timed out; Defender may still be scanning. Check Windows Security before retrying.'}
        except Exception as exc:result={'status':'unavailable','message':str(exc)}
        with _lock:_scan.update(result)
        audit_device_security()
    threading.Thread(target=run,name='JoJo Defender scan',daemon=True).start()
    with _lock:return dict(_scan)

def audit_device_security() -> dict:
    """Read local Windows protection, active Defender threats, startup indicators and Wi-Fi security. Never proves absence of compromise."""
    global _status
    with _audit_lock:
        try:report=assess(probe())
        except Exception as exc:report={'status':'unavailable','checked_at':time.time(),'findings':[],'unknown':['audit'],'summary':str(exc)+' '+LIMITATION}
        important=[f for f in report['findings'] if f['level'] in ('high','critical')]
        report['alert_id']=hashlib.sha256(json.dumps(important,sort_keys=True).encode()).hexdigest()[:20] if important else ''
        with _lock:_status=report
        try:
            target=DATA_DIR/'jojo_security_latest.json';tmp=target.with_suffix('.tmp')
            tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');tmp.replace(target)
        except OSError:pass
        return copy.deepcopy(report)

def inspect_app_file(path: str) -> dict:
    """Read a local app file's SHA256 and Authenticode signature without executing or uploading it. Signatures are not a safety guarantee."""
    if path.startswith(('\\\\','//')):raise ValueError('Only a local file is supported; network shares are not contacted.')
    target=Path(path).expanduser().resolve(strict=True)
    if str(target).startswith(('\\\\','//')):raise ValueError('Resolved file is on a network share; inspection refused.')
    if not target.is_file() or target.stat().st_size>512*1024*1024:raise ValueError('Choose a regular file up to 512 MiB.')
    digest=hashlib.sha256()
    with target.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
    try:signature=probe('file',target).get('signature',{})
    except Exception:signature={'available':False,'error':'Signature inspection unavailable.'}
    return {'file':target.name,'sha256':digest.hexdigest(),'signature':signature,'executed':False,'uploaded':False,
            'limitation':'Valid signatures identify a publisher; unsigned files are not automatically malware. '+LIMITATION}

def wifi_security_guidance() -> str:
    """Defensive steps for the user's own Wi-Fi; never extracts passwords or attacks networks."""
    return 'Apne router par WPA3-Personal ya WPA2-AES use karein; unique long Wi-Fi/admin passwords, firmware updates, WPS off, aur guest/IoT network separation check karein. JoJo Wi-Fi passwords crack/export, deauthentication, ya unauthorized network attacks nahi karta. Device audit sirf current authentication indicators check karta hai.'

def format_report(report):
    lines=[report.get('summary',LIMITATION)]
    for finding in report.get('findings',[]):
        lines.append(f"[{finding['level']}] {finding['message']}"+(' Next: '+finding['action'] if finding.get('action') else ''))
    if report.get('unknown'):lines.append('Unavailable: '+', '.join(report['unknown']))
    return '\n'.join(lines)

def security_command(message):
    low=message.casefold()
    if low.startswith(('app check ', 'file safety check ')):
        prefix='app check ' if low.startswith('app check ') else 'file safety check '
        try:
            result=inspect_app_file(message[len(prefix):].strip().strip('"'))
            return json.dumps(result,ensure_ascii=False,indent=2)
        except (OSError,ValueError) as exc:return 'App inspection unavailable: '+str(exc)
    if any(word in low for word in ('link check','check link','link safe','url check','link risk','link scan')):
        match=re.search(r'https?://[^\s<>"\']+',message,re.I)
        return format_report(inspect_link(match.group().rstrip('.,)'))) if match else 'Link check ke liye poora http/https URL bhejiye. Link khole bina uske indicators check karunga.'
    if any(word in low for word in ('security check','security audit','device hack','hacked','hack hua','virus check','malware check')):
        return format_report(audit_device_security())
    if re.search(r'\bwi[ -]?fi\b',low) and any(word in low for word in ('hack','secure','security','audit')):
        return wifi_security_guidance()
    return None

def start_security_monitor(stop_event):
    global _worker
    if os.environ.get('JOJO_DISABLE_SECURITY_MONITOR')=='1':return
    if _worker and _worker.is_alive():return
    def run():
        while not stop_event.is_set():
            audit_device_security()
            if stop_event.wait(300):break
    _worker=threading.Thread(target=run,name='JoJo security monitor',daemon=True);_worker.start()

if __name__=='__main__':
    print(format_report(audit_device_security()))
