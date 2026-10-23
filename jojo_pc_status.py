"""Fast, read-only local PC status. No cloud call or automatic process killing."""
import os
import re
from pathlib import Path

def snapshot():
    import psutil
    data={'errors':[]}
    for name,read in [('cpu',lambda:round(psutil.cpu_percent(interval=.2),1)),
                      ('ram',lambda:psutil.virtual_memory()._asdict()),
                      ('disk',lambda:psutil.disk_usage(Path(os.environ.get('SystemRoot','C:/Windows')).anchor or '/')._asdict()),
                      ('battery',lambda:(b._asdict() if (b:=psutil.sensors_battery()) else None))]:
        try:data[name]=read()
        except (OSError,RuntimeError,psutil.Error):data['errors'].append(name)
    return data

def describe(data):
    parts=[]
    if 'cpu' in data:parts.append(f"CPU {data['cpu']}%")
    if 'ram' in data:
        m=data['ram'];parts.append(f"RAM {m['percent']}%, {m['available']/1024**3:.1f} GB available")
    if 'disk' in data:
        d=data['disk'];parts.append(f"System drive {d['free']/1024**3:.1f} GB free")
    if 'battery' in data:
        b=data['battery'];parts.append(f"Battery {b['percent']}%, "+('plugged in' if b['power_plugged'] else 'on battery') if b else 'Battery sensor unavailable')
    if data.get('errors'):parts.append('Unavailable: '+', '.join(data['errors']))
    if data.get('ram',{}).get('percent',0)>=85:parts.append('RAM usage high hai; unused apps review kar sakte hain.')
    if data.get('disk',{}).get('percent',0)>=90:parts.append('Storage low hai; delete karne se pehle files review kijiye.')
    if data.get('cpu',0)>=85:parts.append('CPU ka current sample high hai; ek sample se slowdown ka cause confirm nahi hota.')
    return '. '.join(parts)+'.'

def command(text,source):
    if source!='laptop':return None
    value=re.sub(r'\s+',' ',text.casefold()).strip(' .!?।')
    choices={'pc status','system status','laptop status','pc health','laptop health',
             'battery status','ram usage','cpu usage','storage status','disk space',
             'laptop slow kyu hai','mera laptop slow kyu hai','pc slow kyu hai',
             'बैटरी कितनी है','लैपटॉप का स्टेटस बताओ','लैपटॉप धीमा क्यों है'}
    if value not in choices:return None
    from jojo_capabilities import allowed_tool
    if not allowed_tool('get_pc_system_diagnostics'):return 'PC status skill disabled hai. Dashboard mein enable kar sakte hain.'
    return describe(snapshot())
