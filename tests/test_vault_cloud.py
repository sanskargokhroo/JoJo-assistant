import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch,Mock
import test_mobile_actions as base

class VaultFlowTests(unittest.TestCase):
    setUp=base.CompanionFlowTests.setUp
    voice=base.CompanionFlowTests.voice
    step=base.CompanionFlowTests.step
    def test_owner_unlock_grant_contains_no_pin_and_verifies_result(self):
        reply=self.voice('JoJo unlock phone').json();action=reply['action'];session=reply['session']
        self.assertEqual(action['type'],'prepare_unlock');self.assertNotIn('pin',action)
        next_action=self.step(session,device_locked=True,result='unlock preparing: normal authentication screen requested').json()['action']
        self.assertEqual(next_action['type'],'unlock_saved')
        self.assertEqual(next_action['command_id'],action['command_id'])
        done=self.step(session,unlock_verified_id=action['command_id'],result='unlock submitted').json()
        self.assertIn('verify ho gaya',done['reply'])
    def test_failed_unlock_cannot_automatically_repeat(self):
        reply=self.voice('JoJo unlock phone').json();session=reply['session']
        result=self.step(session,device_locked=True,result='unlock unavailable').json()
        self.assertEqual(result['action']['type'],'finish')
        self.assertEqual(self.step(session,device_locked=True).status_code,409)
    def test_unverified_voice_cannot_access_vault(self):
        self.core.verify_boss.return_value=False
        self.assertEqual(self.voice('JoJo unlock phone').json()['state'],'access_denied')
    def test_other_device_cannot_use_unlock_session(self):
        session=self.voice('JoJo unlock phone').json()['session']
        self.assertEqual(self.step(session,device='phone-b',device_locked=True).status_code,403)
    def test_auto_unlock_only_when_native_reports_saved_exact_scope(self):
        session=self.voice('JoJo WhatsApp kholo').json()['session']
        result=self.step(session,package='com.whatsapp',auth_required=True,saved_unlock_scope='com.whatsapp').json()
        self.assertEqual(result['action']['scope'],'com.whatsapp')

class CloudTests(unittest.TestCase):
    def setUp(self):
        import jojo_journal as journal
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        p=patch.object(journal,'DATA_DIR',Path(self.temp.name));p.start();self.addCleanup(p.stop)
    def test_same_namespace_both_sources_and_idempotent_outbox(self):
        import jojo_journal as journal
        from jojo_cloud_memory import sync_once,status
        for source in ('mobile','laptop'):
            task={'id':source,'source':source,'device_id':'phone-a' if source=='mobile' else 'laptop','message':'hello','reply':'hi','status':'completed'}
            journal.record(task);journal.record(task)
        self.assertEqual(status()['pending'],2)
        client=Mock();self.assertEqual(sync_once(client),2)
        self.assertEqual(status()['pending'],0)
        self.assertTrue(all(c.args[0]=='jojo_memory' for c in client.collection.call_args_list))
    def test_offline_keeps_queue(self):
        import jojo_journal as journal
        from jojo_cloud_memory import sync_once,status
        journal.record({'id':'a','source':'mobile','message':'hello','status':'completed'})
        client=Mock();client.collection.side_effect=TimeoutError
        with self.assertRaises(TimeoutError):sync_once(client)
        self.assertEqual(status()['pending'],1)
    def test_sensitive_fields_never_enter_cloud_payload(self):
        from jojo_cloud_memory import redact
        value=redact({'pin':'1234','password':'secret','message':'my pin is 1234','device_id':'a'})
        self.assertNotIn('1234',str(value));self.assertNotIn('secret',str(value));self.assertEqual(value['device_id'],'a')
    def test_clear_replaces_pending_records_with_deletions(self):
        import jojo_journal as journal
        from jojo_cloud_memory import sync_once
        journal.record({'id':'a','source':'mobile','message':'hello','status':'completed'})
        journal.clear();client=Mock();sync_once(client)
        doc=client.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc.delete.assert_called_once();doc.set.assert_not_called()

if __name__=='__main__':unittest.main()
