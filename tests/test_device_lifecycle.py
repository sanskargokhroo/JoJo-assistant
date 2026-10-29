import unittest
from unittest.mock import patch, Mock
import threading
from fastapi.testclient import TestClient

class DeviceLifecycleTests(unittest.TestCase):
    def setUp(self):
        import jojo_core
        self.core=jojo_core
        self.api=TestClient(jojo_core.app)
        for name in ('desktop_deactivated','microphone_paused','shutdown_requested'):
            p=patch.object(jojo_core,name,threading.Event());p.start();self.addCleanup(p.stop)
        p=patch.object(jojo_core,'save_preferences');p.start();self.addCleanup(p.stop)

    def test_laptop_deactivate_preserves_backend_and_mobile_status(self):
        with patch.object(self.core.task_manager,'cancel_pending') as cancel,patch.object(self.core,'stop_speech'),patch('jojo_android.pairing_key',return_value='test-pair'):
            result=self.api.post('/api/desktop/deactivate').json()
            self.assertEqual(result['mobile_service'],'available')
            cancel.assert_called_once_with('laptop')
            self.assertFalse(self.core.shutdown_requested.is_set())
            self.assertTrue(self.core.microphone_paused.is_set())
            phone=self.api.get('/api/mobile/status',headers={'X-JoJo-Key':'test-pair'})
            self.assertEqual(phone.status_code,200)
            self.assertFalse(phone.json()['laptop_active'])

    def test_status_requires_pairing(self):
        self.assertEqual(self.api.get('/api/mobile/status').status_code,401)

    def test_reactivate_restores_laptop(self):
        self.core.desktop_deactivated.set();self.core.microphone_paused.set()
        self.assertEqual(self.api.post('/api/desktop/activate').status_code,200)
        self.assertFalse(self.core.desktop_deactivated.is_set())
        self.assertFalse(self.core.microphone_paused.is_set())

    def test_deactivated_desktop_rejects_actions(self):
        self.core.desktop_deactivated.set()
        with self.assertRaisesRegex(ValueError,'deactivated'):
            self.core.dispatch_command('open calculator','laptop')

    def test_phone_stop_does_not_stop_laptop_speech(self):
        with patch.object(self.core,'stop_speech') as speech,patch.object(self.core.task_manager,'cancel_pending',return_value={}) as cancel:
            self.api.post('/api/tasks',json={'message':'stop','source':'mobile'})
            cancel.assert_called_once_with('mobile');speech.assert_not_called()

    def test_phone_task_does_not_speak_on_laptop(self):
        with patch.object(self.core,'stop_speech') as speech,patch.object(self.core.task_manager,'submit',return_value={'id':'test'}) as submit:
            self.api.post('/api/tasks',json={'message':'what time is it','source':'mobile','speak':True})
            self.assertFalse(submit.call_args.args[2]);speech.assert_not_called()

    def test_desktop_ui_deactivation_does_not_call_global_shutdown(self):
        from jojo_desktop import JoJoDesktop
        import queue
        instance=object.__new__(JoJoDesktop)
        instance.stopping=False;instance.detail=Mock();instance.ambient=Mock();instance.events=queue.Queue()
        class InlineThread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch('jojo_desktop.threading.Thread',InlineThread),patch('jojo_desktop.request') as request:
            instance.stop_assistant()
            request.assert_called_once_with('/api/desktop/deactivate',{},timeout=5)
            self.assertEqual(instance.events.get()[0],'shutdown')

if __name__=='__main__':unittest.main()
