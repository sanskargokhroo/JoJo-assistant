import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jojo_mobile_speech import register

class PhoneVoiceTests(unittest.TestCase):
    def setUp(self):
        self.core=Mock();self.core.VOICE_PARAMS={'voice':'hi-IN-MadhurNeural'}
        app=FastAPI()
        def authenticate(req):
            if req.headers.get('x-jojo-key')!='test':raise HTTPException(401)
        register(app,self.core,authenticate);self.api=TestClient(app)
        self.paths=[]
        def synth(text,path):
            self.paths.append(Path(path));Path(path).write_bytes(b'a'*500);return True
        self.core.synthesize_sync.side_effect=synth
        self.private=patch('jojo_workspace.private_session',return_value=False);self.private.start();self.addCleanup(self.private.stop)

    def test_uses_selected_synthesis_without_laptop_playback(self):
        result=self.api.post('/api/mobile/speech',headers={'X-JoJo-Key':'test'},json={'text':'Namaste'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.headers['x-jojo-voice'],'hi-IN-MadhurNeural')
        self.assertEqual(result.content,b'a'*500)
        self.core.speak.assert_not_called()
        self.assertTrue(all(not p.exists() for p in self.paths))

    def test_private_session_does_not_send_to_online_voice(self):
        with patch('jojo_workspace.private_session',return_value=True):
            result=self.api.post('/api/mobile/speech',headers={'X-JoJo-Key':'test'},json={'text':'private'})
        self.assertEqual(result.status_code,409);self.core.synthesize_sync.assert_not_called()

    def test_failure_does_not_choose_another_voice(self):
        self.core.synthesize_sync.side_effect=RuntimeError('offline')
        result=self.api.post('/api/mobile/speech',headers={'X-JoJo-Key':'test'},json={'text':'hello'})
        self.assertEqual(result.status_code,503);self.core.speak.assert_not_called()

    def test_authentication_and_payload_limit(self):
        self.assertEqual(self.api.post('/api/mobile/speech',json={'text':'hello'}).status_code,401)
        self.assertEqual(self.api.post('/api/mobile/speech',headers={'X-JoJo-Key':'test'},json={'text':'x'*3001}).status_code,422)
        self.core.synthesize_sync.assert_not_called()
