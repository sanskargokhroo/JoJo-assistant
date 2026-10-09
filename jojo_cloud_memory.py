"""One shared Firestore outbox for both sources. PIN vault data never enters here."""
import json
import os
import re
import threading
import time
from jojo_journal import connect

_client=None
_status={'configured':False,'last_success':None,'error':None}

def tables(db):
    db.execute('CREATE TABLE IF NOT EXISTS cloud_memory_outbox (key TEXT PRIMARY KEY, payload TEXT, updated REAL)')

def namespace():
    name=os.environ.get('JOJO_MEMORY_NAMESPACE','primary')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name):raise ValueError('Invalid memory namespace')
    return name

def redact(value):
    if isinstance(value,dict):return {k:('[redacted]' if re.search(r'pin|password|secret|token|audio|pairing|credential',k,re.I) else redact(v)) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,str) and re.search(r'\b(pin|password|passcode|api.?key|token)\b\s*(?:is|hai|=|:|ye hai)\s*\S+|(?:पिन|पासवर्ड)\s*(?:है|[:=])\s*\S+',value,re.I):return '[credential-like text omitted]'
    return value

def enqueue(kind,identifier,payload):
    if kind not in {'turns','workflows','corrections'}:raise ValueError('Unknown memory type')
    import hashlib
    key=kind+'/'+hashlib.sha256(identifier.encode()).hexdigest()
    with connect() as db:
        tables(db)
        db.execute('INSERT OR REPLACE INTO cloud_memory_outbox VALUES (?,?,?)',(key,json.dumps(redact(payload),ensure_ascii=False),time.time()))

def queue_delete(kind,identifier):
    enqueue(kind,identifier,{'__delete__':True})

def sync_once(client):
    with connect() as db:
        tables(db);rows=db.execute('SELECT key,payload,updated FROM cloud_memory_outbox ORDER BY updated LIMIT 25').fetchall()
    for key,payload,updated in rows:
        kind,identifier=key.split('/')
        doc=client.collection('jojo_memory').document(namespace()).collection(kind).document(identifier)
        value=json.loads(payload)
        if value=={'__delete__':True}:doc.delete(timeout=8,retry=None)
        else:doc.set(value,timeout=8,retry=None)
        with connect() as db:
            db.execute('DELETE FROM cloud_memory_outbox WHERE key=? AND updated=?',(key,updated))
        _status.update(last_success=time.time(),error=None)
    return len(rows)

def status():
    with connect() as db:
        tables(db);pending=db.execute('SELECT count(*) FROM cloud_memory_outbox').fetchone()[0]
    return dict(_status,namespace=namespace(),pending=pending,shared_sources=['laptop','mobile'],pin_storage='phone-local only')

def start(client,stop):
    global _client
    _client=client;_status['configured']=client is not None and os.environ.get('JOJO_DISABLE_CLOUD')!='1'
    if not _status['configured']:return
    def worker():
        while not stop.is_set():
            try:sync_once(client)
            except Exception as exc:_status['error']=type(exc).__name__
            stop.wait(15)
    threading.Thread(target=worker,name='JoJo shared memory sync',daemon=True).start()
