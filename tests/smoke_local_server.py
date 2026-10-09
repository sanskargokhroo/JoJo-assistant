"""Real core startup/API/shutdown check, with no microphone, cloud, or OS actions."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix='jojo-server-smoke-') as state:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, JOJO_DATA_DIR=state, JOJO_PORT=str(port), JOJO_HOST='127.0.0.1',
            JOJO_DISABLE_CLOUD='1', JOJO_NO_OVERLAY='1', JOJO_DISABLE_SECURITY_MONITOR='1', PYTHONUTF8='1', PYTHONUNBUFFERED='1')
        with open(Path(state) / 'core.log', 'w+', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'jojo_core.py'), '--no-voice'],
                cwd=str(ROOT), env=env, stdout=log, stderr=log,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            def api(path, data=None):
                req = urllib.request.Request(f'http://127.0.0.1:{port}' + path,
                    data=json.dumps(data).encode() if data is not None else None,
                    headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('Test core exited early (another JoJo core may already be running).')
                    try:
                        health = api('/api/health')
                        break
                    except OSError:
                        time.sleep(.2)
                else:
                    raise RuntimeError('Test core did not become ready.')
                assert health['service'] == 'jojo' and health['version'] == 2
                workspace=api('/api/workspace')
                assert workspace['cards']==[] and workspace['history']==[]
                card=api('/api/workspace',{'action':'save_memory','text':'Fixture preference'})
                assert len(api('/api/workspace')['cards'])==1
                api('/api/workspace',{'action':'delete_memory','id':card['id']})
                assert api('/api/workspace')['cards']==[]
                # A blocked command exercises the worker without doing any external work.
                command={'message':'otp','speak':False,'request_id':'smoke-deduplication'}
                task = api('/api/tasks', command)
                assert api('/api/tasks',command)['id']==task['id']
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    result = api('/api/tasks/' + task['id'])
                    if result['status'] == 'needs_input':
                        break
                    time.sleep(.05)
                assert result['status'] == 'needs_input', result
                state_response = api('/api/voice_state')
                assert 'transcript' in state_response and 'reply' in state_response
                assert api('/api/shutdown', {})['status'] == 'shutting_down'
                process.wait(timeout=8)
                assert process.returncode == 0
                print('PASS: real core startup, workspace memory API, task worker, voice-state contract and graceful shutdown.')
            except Exception:
                log.flush()
                log.seek(0)
                print(log.read()[-6000:])
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)

if __name__ == '__main__':
    main()
