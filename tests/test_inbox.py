"""Inbox reads and follow-up replies: fixtures only, no personal messages or sends."""
import json
import unittest
from unittest.mock import patch
import test_mobile_actions as base
from jojo_inbox import read_mode, report_items, offer, advance, empty_report, read_action_allowed

class InboxUnitTests(unittest.TestCase):
    def test_hinglish_and_hindi_intents(self):
        self.assertEqual(read_mode('WhatsApp par kiski chats unread hain'),'whatsapp')
        self.assertEqual(read_mode('व्हाट्सएप पर किसके मैसेज आए हैं'),'whatsapp')
        self.assertEqual(read_mode('kiska call aaya'),'calls')
        self.assertEqual(read_mode('किसका मैसेज आया'),'messages')
        self.assertEqual(read_mode('WhatsApp kholo'),'')

    def test_no_invented_sender_or_cross_screen_message(self):
        with self.assertRaises(ValueError):report_items([{'sender':'Rahul','text':'secret'}],['Rahul: hello','Neha: secret'])
        self.assertEqual(report_items([{'sender':'Rahul','text':'hello'}],['Rahul: hello'])[0]['text'],'hello')

    def test_yes_always_asks_for_body(self):
        state,result=advance(offer([{'sender':'Rahul','text':'hello'}],'whatsapp'),'haan')
        self.assertEqual(state['phase'],'body');self.assertNotIn('send',result)
        state,result=advance(state,'main kal aaunga')
        self.assertEqual(result['send'],'main kal aaunga');self.assertEqual(result['recipient'],'Rahul')

    def test_multiple_senders_require_selection(self):
        pending=offer([{'sender':'Rahul','text':'hello'},{'sender':'Neha','text':'hi'}],'whatsapp')
        pending,result=advance(pending,'haan');self.assertEqual(pending['phase'],'recipient')
        pending,result=advance(pending,'usko');self.assertNotIn('send',result)
        pending,result=advance(pending,'Neha ko');self.assertEqual(pending['phase'],'body')
        _,result=advance(pending,'reply kr main aa rahi hoon');self.assertEqual(result['send'],'main aa rahi hoon')

    def test_no_closes_and_direct_reply_preserves_body(self):
        state=offer([{'sender':'Rahul','text':'hello'}],'whatsapp')
        self.assertTrue(advance(state,'nahi')[1]['close'])
        self.assertEqual(advance(state,'usko ye reply kr main busy hoon')[1]['send'],'main busy hoon')

    def test_empty_claim_requires_observed_empty_label(self):
        self.assertFalse(empty_report('No unread chats',['Chats: Rahul']))
        self.assertTrue(empty_report('No unread chats',['3: No unread chats']))
        self.assertFalse(empty_report('Rahul',['Rahul']))

    def test_read_phase_cannot_send_type_message_or_call(self):
        for label in ['Send','Call Rahul','Delete chat']:
            self.assertFalse(read_action_allowed({'type':'click','node':1},'1: '+label,'whatsapp'))
        self.assertFalse(read_action_allowed({'type':'type','node':1},'1: Message','whatsapp'))
        self.assertTrue(read_action_allowed({'type':'type','node':1},'1: Search','whatsapp'))
        self.assertTrue(read_action_allowed({'type':'click','node':1},'1: Recents','calls'))
        self.assertFalse(read_action_allowed({'type':'click','node':1},'1: Rahul','calls'))
        self.assertFalse(read_action_allowed({'type':'click','node':1},'1: कॉल','calls'))

class InboxFlowTests(unittest.TestCase):
    setUp=base.CompanionFlowTests.setUp
    voice=base.CompanionFlowTests.voice
    step=base.CompanionFlowTests.step

    def report(self,session,screen='0: Rahul\n1: Kal milte hain',items=None):
        if items is None:items=[{'sender':'Rahul','text':'Kal milte hain'}]
        with patch('jojo_android.make_client') as model:
            model.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'finish','status':'completed','read_items':items})
            return self.step(session,package='com.whatsapp',app_role='whatsapp',screen=screen).json()

    def test_full_read_yes_dictation_flow(self):
        session=self.voice('JoJo WhatsApp unread msg read karo').json()['session']
        read=self.report(session);self.assertIn('Sir, koi reply',read['reply'])
        yes=self.voice('haan',session).json();self.assertIn('kya reply',yes['reply'])
        self.assertEqual(yes['action']['type'],'finish')
        body=self.voice('main kal aaunga',session).json();self.assertEqual(body['action']['type'],'observe')
        with patch('jojo_android.make_client') as model:
            model.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'type','node':3,'text':'main kal aaunga'})
            result=self.step(session,package='com.whatsapp',screen='0: Rahul\n3: Message editable=true').json()
        self.assertEqual(result['action']['reply_recipient'],'Rahul')
        self.assertEqual(result['action']['reply_body'],'main kal aaunga')
        self.assertTrue(result['action']['reply_id'])

    def test_no_leaves_only_requested_app_and_verifies(self):
        session=self.voice('JoJo WhatsApp unread read karo').json()['session'];self.report(session)
        result=self.voice('nahi',session).json()
        self.assertEqual(result['action'],{'type':'leave_app','package':'com.whatsapp'})
        with patch('jojo_android.make_client') as model:
            done=self.step(session,package='com.android.launcher',result='home sent; verify next screen',screen='Home').json()
        model.assert_not_called();self.assertIn('Home par aa gaya',done['reply'])

    def test_read_request_blocks_model_send(self):
        session=self.voice('JoJo WhatsApp unread read karo').json()['session']
        with patch('jojo_android.make_client') as model:
            model.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'click','node':3})
            result=self.step(session,package='com.whatsapp',app_role='whatsapp',screen='3: Send').json()
        self.assertEqual(result['action']['type'],'finish');self.assertIn('sirf',result['reply'])

    def test_wrong_body_not_sent_and_other_phone_cannot_answer(self):
        session=self.voice('JoJo WhatsApp unread read karo').json()['session'];self.report(session)
        self.assertEqual(self.voice('haan',session,device='phone-b').json()['state'],'sleeping')
        self.voice('haan',session);self.voice('hello',session)
        with patch('jojo_android.make_client') as model:
            model.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'type','node':3,'text':'invented reply'})
            result=self.step(session,package='com.whatsapp',screen='3: Message').json()
        self.assertEqual(result['action']['type'],'finish');self.assertIn('match nahi',result['reply'])

    def test_report_cannot_use_launcher_text_as_whatsapp_evidence(self):
        session=self.voice('JoJo WhatsApp unread read karo').json()['session']
        with patch('jojo_android.make_client') as model:
            model.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'finish','status':'completed','read_items':[{'sender':'Rahul','text':'hello'}]})
            result=self.step(session,package='com.android.launcher',screen='Rahul hello').json()
        self.assertNotIn('Sir, koi reply',result['reply'])

    def test_send_success_requires_matching_native_verification_id(self):
        session=self.voice('JoJo WhatsApp unread read karo').json()['session'];self.report(session)
        self.voice('haan',session);self.voice('hello',session)
        with patch('jojo_android.make_client') as model:
            model.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'finish','status':'completed','reply':'Sent!'})
            result=self.step(session,package='com.whatsapp',screen='Rahul hello',reply_verified_id='invented').json()
        self.assertIn('verify nahi hua',result['reply'])

    def test_owner_mismatch_revokes_pending_reply(self):
        session=self.voice('JoJo WhatsApp unread read karo').json()['session'];self.report(session)
        self.core.verify_boss.return_value=False
        self.assertEqual(self.voice('haan',session).json()['state'],'access_denied')
        self.core.verify_boss.return_value=True
        self.assertEqual(self.voice('haan',session).json()['state'],'sleeping')

    def test_fresh_wake_cannot_reuse_expired_pending_reply(self):
        session=self.voice('JoJo WhatsApp unread read karo').json()['session'];self.report(session)
        with patch('jojo_android.time.monotonic',return_value=10**12):
            result=self.voice('JoJo haan',session).json()
        self.assertEqual(result['action']['type'],'observe')
        self.assertNotIn('kya reply',result.get('reply',''))

if __name__=='__main__':unittest.main()
