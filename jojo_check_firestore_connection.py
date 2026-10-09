"""Read-only connectivity check; never prints credentials or document contents."""
import json
import os
from jojo_config import ROOT

def main():
    if os.environ.get('JOJO_DISABLE_CLOUD')=='1':
        print(json.dumps({'configured':False,'reason':'cloud disabled'}));return
    try:
        import firebase_admin
        from firebase_admin import credentials,firestore
        from jojo_config import firebase_credential
        configured=firebase_credential()
        if not configured:raise RuntimeError('Configure your Firebase project in setup first.')
        app=firebase_admin.initialize_app(credentials.Certificate(configured),name='jojo-memory-read-check')
        client=firestore.client(app)
        next(iter(client.collection('jojo_memory').limit(1).stream(timeout=8,retry=None)),None)
        print(json.dumps({'configured':True,'read_verified':True,'project':app.project_id}))
    except Exception as exc:
        print(json.dumps({'read_verified':False,'error_type':type(exc).__name__}));raise SystemExit(1)

if __name__=='__main__':main()
