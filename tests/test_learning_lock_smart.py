import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_mobile_actions as base
from jojo_device_lock import lock_intent,desktop_command,UNLOCK_REPLY
from jojo_learning import owner_command,learning_context
from jojo_smart_home import control_smart_device,list_smart_devices

class LearningTests(unittest.TestCase):
    def test_outcomes_idempotent_corrections_retrieved_and_clear(self):
        import jojo_journal as journal
        with tempfile.TemporaryDirectory() as tmp,patch.object(journal,'DATA_DIR',Path(tmp)):
            task={'id':'a','source':'mobile','message':'open WhatsApp','reply':'failed','status':'incomplete'}
            journal.record(task);journal.record(task)
            self.assertIn('yaad',owner_command('yaad rakho short answers dena'))
            self.assertIn('short answers',learning_context('WhatsApp'))
            self.assertIn('incomplete',learning_context('WhatsApp'))
            self.assertIn("'incomplete': 1",owner_command('learning status'))
            self.assertIn('save nahi',owner_command('yaad rakho password secret'))
            journal.clear();self.assertEqual(learning_context('WhatsApp'),'')

class LockTests(unittest.TestCase):
    def test_explicit_lock_and_unlock_distinguished(self):
        for device in ['laptop','pc','computer']:
            self.assertEqual(lock_intent('lock the '+device,'mobile'),('lock','laptop'))
            self.assertEqual(lock_intent('unlock the '+device,'mobile'),('unlock','laptop'))
        self.assertEqual(lock_intent('phone lock karo','laptop'),('lock','mobile'))
        for text in ['how to lock phone','lock mat karo','lock screen design improve','phone is locked','clock kholo']:
            self.assertIsNone(lock_intent(text,'laptop'))

    def test_unlock_never_invokes_lock_or_credential_entry(self):
        with patch('jojo_device_lock.request_windows_lock') as lock:
            self.assertEqual(desktop_command('unlock pc'),UNLOCK_REPLY)
            desktop_command('lock phone')
        lock.assert_not_called()

class MobileLockTests(unittest.TestCase):
    setUp=base.CompanionFlowTests.setUp
    voice=base.CompanionFlowTests.voice
    step=base.CompanionFlowTests.step
    def test_verified_lock_observes_keyguard_then_revokes_session(self):
        result=self.voice('JoJo lock the phone').json();session=result['session']
        self.assertEqual(result['action']['type'],'lock_device')
        done=self.step(session,device_locked=True,result='lock requested').json()
        self.assertIn('locked',done['reply']);self.assertTrue(done['sleep_after'])
        self.assertEqual(self.step(session).status_code,403)
    def test_unlock_handoff_and_locked_observation_never_use_model(self):
        with patch('jojo_android.make_client') as model:
            result=self.voice('JoJo unlock phone').json()
            self.assertEqual(result['action']['type'],'prepare_unlock')
            denied=self.step(result['session'],device_locked=True,result='unlock unavailable: local vault not configured').json()
            self.assertIn('manually',denied['reply'])
            session=self.voice('JoJo WhatsApp kholo').json()['session']
            self.assertEqual(self.step(session,device_locked=True).json()['reply'],UNLOCK_REPLY)
            session=self.voice('JoJo WhatsApp kholo').json()['session']
            self.assertEqual(self.step(session,auth_required=True).json()['reply'],UNLOCK_REPLY)
        model.assert_not_called()
    def test_unverified_owner_cannot_lock(self):
        self.core.verify_boss.return_value=False
        result=self.voice('JoJo lock phone').json()
        self.assertEqual(result['state'],'access_denied');self.assertNotIn('action',result)

class SmartTests(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{'JOJO_HA_URL':'http://127.0.0.1:8123','JOJO_HA_TOKEN':'test-only','JOJO_HA_ENTITIES':'light.room,lock.front'})
        p.start();self.addCleanup(p.stop)
    def test_allowlist_and_domain_prevent_arbitrary_actions(self):
        with patch('jojo_smart_home.request') as send:
            self.assertIn('allowlist',control_smart_device('light.other','on'))
            self.assertIn('Only on/off',control_smart_device('lock.front','on'))
        send.assert_not_called()
    def test_action_verified_without_retry(self):
        with patch('jojo_smart_home.request',side_effect=[{'state':'off'},[],{'state':'on'}]) as send:
            self.assertIn('Verified',control_smart_device('light.room','on'))
        self.assertEqual(send.call_count,3)
    def test_uncertain_response_not_repeated(self):
        with patch('jojo_smart_home.request',side_effect=[{'state':'off'},TimeoutError]) as send:
            self.assertIn('No automatic retry',control_smart_device('light.room','on'))
        self.assertEqual(send.call_count,2)
    def test_unconfigured_does_not_scan_network(self):
        with patch.dict(os.environ,{'JOJO_HA_TOKEN':''}),patch('jojo_smart_home.request') as send:
            self.assertIn('setup pending',list_smart_devices())
        send.assert_not_called()

if __name__=='__main__':unittest.main()
