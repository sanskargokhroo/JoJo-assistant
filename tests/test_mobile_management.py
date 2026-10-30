import test_00_isolation
import unittest
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jojo_mobile_management import register


class ManagementTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI()
        def auth(request):
            if request.headers.get('x-jojo-key')!='fixture':raise HTTPException(401)
        register(app,auth)
        self.client=TestClient(app)
        self.headers={'x-jojo-key':'fixture'}

    def test_management_requires_pairing(self):
        self.assertEqual(self.client.get('/api/mobile/management').status_code,401)
        self.assertEqual(self.client.post('/api/mobile/management/memory',json={'remember_tasks':False}).status_code,401)

    def test_status_never_exposes_credentials(self):
        with patch('jojo_user_config.load',return_value={'api_key':'private-fixture','firebase':{'private_key':'firebase-fixture'}}),patch('jojo_config.api_keys',return_value=['private-fixture']):
            response=self.client.get('/api/mobile/management',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertNotIn('private-fixture',response.text)
        self.assertNotIn('firebase-fixture',response.text)

    def test_phone_cannot_disable_management_or_change_desktop(self):
        for key in ['mobile','desktop']:
            response=self.client.post('/api/mobile/management/skills',headers=self.headers,json={key:False})
            self.assertEqual(response.status_code,400)

    def test_memory_switch_validates_boolean(self):
        self.assertEqual(self.client.post('/api/mobile/management/memory',headers=self.headers,json={'remember_tasks':'false'}).status_code,400)
        with patch('jojo_config.save_preferences') as save:
            self.assertEqual(self.client.post('/api/mobile/management/memory',headers=self.headers,json={'remember_tasks':False}).status_code,200)
            save.assert_called_once_with({'remember_tasks':False})

    def test_memory_disabled_and_secret_turns_not_saved(self):
        from jojo_journal import record
        task={'id':'privacy-fixture','source':'mobile','message':'my PIN is 1234','status':'completed'}
        with patch('jojo_journal.connect') as connect,patch('jojo_workspace.private_session',return_value=False):
            record(task);connect.assert_not_called()
            with patch('jojo_config.read_preferences',return_value={'remember_tasks':False}):
                record(dict(task,message='open gallery'));connect.assert_not_called()
