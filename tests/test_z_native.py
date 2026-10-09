"""Native wake, owner gating, app policy and persistent-memory regressions."""
import base64
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch, Mock
import numpy as np
from jojo_ambient import overlay_state
from jojo_policy import blocked_reason, guard_tool, guard_desktop

class NativeTests(unittest.TestCase):
    def test_idle_and_paused_never_show_overlay(self):
        self.assertIsNone(overlay_state({'status':'speaking','active_session':False}))
        self.assertIsNone(overlay_state({'status':'listening','active_session':True,'microphone_paused':True}))

    def test_overlay_follows_voice_and_task(self):
        self.assertEqual(overlay_state({'status':'speaking','active_session':True}), 'speaking')
        self.assertEqual(overlay_state({'status':'thinking','active_session':True,'task':{'status':'running','events':[{}]}}), 'working')

    def test_all_requested_restricted_apps_and_aliases(self):
        for value in ['open Paytm','paytm.in','binance','Trust Wallet','com.wallet.crypto.trustapp','pay\u200btm','Ｐａｙｔｍ','trust-wallet','groww']:
            self.assertIsNotNone(blocked_reason(value),value)
        self.assertIsNone(blocked_reason('open calculator'))

    def test_foreground_restricted_app_blocks_action(self):
        with patch('jojo_policy.foreground_title',return_value='Paytm - Chrome'):
            with self.assertRaises(PermissionError):guard_desktop('scroll down')

    def test_code_tools_cannot_bypass_restrictions(self):
        for name in ['run_python_code','run_powershell','create_new_persistent_skill','send_http_request']:
            with self.assertRaises(PermissionError):guard_tool(name,{})

    def test_memory_survives_new_connection_and_closes_files(self):
        import jojo_journal as journal
        with tempfile.TemporaryDirectory() as directory, patch.object(journal,'DATA_DIR',Path(directory)):
            journal.record({'id':'a','source':'laptop','message':'My preferred editor is Notepad','reply':'Remembered','status':'completed','events':[]})
            self.assertIn('Notepad',journal.recall('editor'))
            journal.remember_workflow('notes','Open Notepad and write the requested note.')
            self.assertIn('Saved workflows',journal.context('note'))
            journal.clear()
            self.assertEqual(journal.recall('editor'),'')
        self.assertFalse(Path(directory).exists())

class VoiceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import jojo_core
        from fastapi.testclient import TestClient
        cls.core=jojo_core;cls.api=TestClient(jojo_core.app)

    def test_missing_owner_profile_denies_even_good_audio(self):
        with patch.object(self.core,'boss_profile',None):
            self.assertFalse(self.core.verify_boss(np.ones(16000,dtype=np.int16)*1000))

    def test_silent_owner_audio_denied(self):
        self.assertFalse(self.core.verify_boss(np.zeros(16000,dtype=np.int16)))

    def test_claiming_boss_without_audio_cannot_wake(self):
        res=self.api.post('/api/voice_command',json={'command':'JoJo open calculator','speaker':'boss'})
        self.assertFalse(res.json()['allowed'])
        self.assertEqual(self.api.post('/api/wake_session?speaker=boss').json()['status'],'denied')

    def test_direct_pc_command_cannot_wake(self):
        with patch.object(self.core,'listen_command',side_effect=[('open calculator',np.ones(16000)),KeyboardInterrupt]), \
             patch.object(self.core,'is_active_session',False),patch.object(self.core,'verify_boss') as verify:
            self.core.microphone_paused.clear()
            with self.assertRaises(KeyboardInterrupt):self.core.run_voice_loop()
            verify.assert_not_called()

    def test_paytm_refused_by_direct_legacy_handler(self):
        with patch.object(self.core,'speak'):
            self.assertEqual(self.core.execute_pc_tasks('open paytm'),self.core.SECURITY_REFUSAL_MSG)

    def test_shopping_sites_open_on_correct_desktop_domain(self):
        for shop,domain in [('amazon','amazon.in'),('flipkart','flipkart.com')]:
            with patch.object(self.core,'open_url_in_chrome') as launch,patch.object(self.core,'extract_shopping_query',return_value='blue shirt'):
                self.core.execute_pc_tasks(shop+' par blue shirt search',source='laptop')
            self.assertIn(domain,launch.call_args.args[0])
            self.assertIn('blue%20shirt',launch.call_args.args[0])

    def test_unhandled_phone_launch_never_opens_laptop_browser(self):
        with patch.object(self.core,'open_url_in_chrome') as launch:
            reply=self.core.execute_pc_tasks('Amazon kholo',source='mobile')
        launch.assert_not_called();self.assertIn('native Android',reply)

    def test_mobile_requires_pairing_key(self):
        self.assertEqual(self.api.post('/api/mobile/voice',json={}).status_code,401)

    def test_mobile_session_cannot_be_forged(self):
        with patch('jojo_android.pairing_key',return_value='test-pair'):
            res=self.api.post('/api/mobile/step',headers={'X-JoJo-Key':'test-pair'},json={'session':'invented'})
            self.assertEqual(res.status_code,403)

    def test_mobile_wake_still_requires_owner_match(self):
        audio=base64.b64encode((np.ones(16000,dtype=np.int16)*1000).tobytes()).decode()
        with patch('jojo_android.pairing_key',return_value='test-pair'),patch('speech_recognition.Recognizer.recognize_google',return_value='JoJo open calculator'),patch.object(self.core,'boss_profile',None):
            result=self.api.post('/api/mobile/voice',headers={'X-JoJo-Key':'test-pair'},json={'audio':audio}).json()
            self.assertEqual(result['state'],'access_denied')

    def test_mobile_background_speech_stays_asleep(self):
        audio=base64.b64encode((np.ones(16000,dtype=np.int16)*1000).tobytes()).decode()
        with patch('jojo_android.pairing_key',return_value='test-pair'),patch('speech_recognition.Recognizer.recognize_google',return_value='open calculator'),patch.object(self.core,'verify_boss') as verify:
            result=self.api.post('/api/mobile/voice',headers={'X-JoJo-Key':'test-pair'},json={'audio':audio}).json()
            self.assertEqual(result['state'],'sleeping');verify.assert_not_called()

    def test_verified_mobile_requests_screen_only_after_wake(self):
        audio=base64.b64encode((np.ones(16000,dtype=np.int16)*1000).tobytes()).decode()
        with patch('jojo_android.pairing_key',return_value='test-pair'),patch('speech_recognition.Recognizer.recognize_google',return_value='JoJo open calculator'),patch.object(self.core,'verify_boss',return_value=self.core.BiometricResult(True,.99)),patch('jojo_android.make_client') as model:
            result=self.api.post('/api/mobile/voice',headers={'X-JoJo-Key':'test-pair'},json={'audio':audio}).json()
            self.assertEqual(result['action']['type'],'observe')
            model.assert_not_called()
            denied=self.api.post('/api/mobile/step',headers={'X-JoJo-Key':'test-pair'},json={'session':result['session'],'package':'net.one97.paytm','screen':'private data'}).json()
            self.assertEqual(denied['action']['type'],'finish');model.assert_not_called()

    def test_mobile_disconnect_never_targets_laptop(self):
        from jojo_agi.jojo_ui_tars_operator import UITarsUnifiedOperator
        operator=object.__new__(UITarsUnifiedOperator)
        operator.target='mobile';operator.mobile=Mock();operator.mobile.is_available.return_value=False
        operator.desktop=Mock()
        with self.assertRaises(RuntimeError):operator.execute_action({'action_type':'click'})
        operator.desktop.execute_action.assert_not_called()

    def test_mobile_sleep_revokes_owner_session(self):
        audio=base64.b64encode((np.ones(16000,dtype=np.int16)*1000).tobytes()).decode()
        headers={'X-JoJo-Key':'test-pair'}
        with patch('jojo_android.pairing_key',return_value='test-pair'),patch('speech_recognition.Recognizer.recognize_google',side_effect=['JoJo','sleep']),patch.object(self.core,'verify_boss',return_value=self.core.BiometricResult(True,.99)):
            wake=self.api.post('/api/mobile/voice',headers=headers,json={'audio':audio}).json()
            asleep=self.api.post('/api/mobile/voice',headers=headers,json={'audio':audio,'session':wake['session']}).json()
            self.assertEqual(asleep['state'],'sleeping')
            result=self.api.post('/api/mobile/step',headers=headers,json={'session':wake['session']})
            self.assertEqual(result.status_code,403)

if __name__=='__main__':unittest.main()
