"""Temporary capability overrides expire and disappear when JoJo restarts."""
import threading
import time

_lock=threading.RLock()
_overrides={}

def set_temporary(group, enabled, minutes=15):
    from jojo_capabilities import CATALOG
    if group not in CATALOG or type(enabled) is not bool or type(minutes) is not int or not 1<=minutes<=120:
        raise ValueError('Choose a known capability, true/false, and 1–120 minutes.')
    with _lock:_overrides[group]=(enabled,time.monotonic()+minutes*60)

def remove(group):
    with _lock:_overrides.pop(group,None)

def effective(group, default):
    with _lock:
        entry=_overrides.get(group)
        if not entry:return default
        if entry[1]<=time.monotonic():
            _overrides.pop(group,None);return default
        return entry[0]

def snapshot():
    from jojo_capabilities import CATALOG,enabled
    with _lock:
        return [{'id':group,'name':value[0],'enabled':enabled(group),
                 'temporary_seconds':max(0,int(_overrides.get(group,(False,0))[1]-time.monotonic()))}
                for group,value in CATALOG.items()]
