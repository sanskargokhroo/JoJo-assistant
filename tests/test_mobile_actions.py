"""No real calls/messages/installs: deterministic policy and paired session fixtures."""
import base64
import json
import unittest
from unittest.mock import patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jojo_mobile_actions import validate_action, affirmative
from jojo_policy import blocked_reason, guard_desktop, PAYMENT_HANDOFF
from jojo_runtime import bind_device, target_platform

class ActionTests(unittest.TestCase):
    def tearDown(self): bind_device('laptop')

    def test_shopping_allowed_payment_target_denied(self):
        self.assertIsNone(blocked_reason('Amazon com.amazon.mShop.android.shopping Flipkart'))
        for label in ['Buy now','Proceed to pay','Place order','भुगतान','Card number','Amazon Pay','Pay ₹500']:
            with self.assertRaises(PermissionError):
                validate_action({'type':'click','node':2},'', '2: '+label)
        self.assertEqual(validate_action({'type':'type','node':1,'text':'blue shirt'},'', '1: Search')['type'],'type')

    def test_unobserved_node_or_forged_install_grant_rejected(self):
        with self.assertRaises(ValueError):validate_action({'type':'click','node':9},'', '1: Search')
        with self.assertRaises(PermissionError):validate_action({'type':'click','node':1,'install_approved':True},'', '1: Install')
        with self.assertRaises(ValueError):validate_action({'type':'open_store','install_approved':True},'', '')

    def test_store_identity_is_resolved_before_install_question(self):
        with patch('jojo_mobile_actions.store_app_name',return_value='WhatsApp Messenger') as resolve:
            action=validate_action({'type':'open','package':'com.whatsapp'},'', '')
        self.assertEqual(action,{'type':'request_install','package':'com.whatsapp','name':'WhatsApp Messenger'})
        resolve.assert_called_once_with('com.whatsapp')

    def test_installed_app_launch_does_not_resolve_store(self):
        with patch('jojo_mobile_actions.store_app_name') as resolve:
            action=validate_action({'type':'open','package':'com.whatsapp'},'WhatsApp = com.whatsapp\n','')
        self.assertEqual(action['type'],'open');resolve.assert_not_called()

    def test_finish_can_explain_restricted_screen(self):
        self.assertEqual(validate_action({'type':'finish','reply':PAYMENT_HANDOFF},'', '')['type'],'finish')

    def test_device_context_does_not_fall_back(self):
        bind_device('mobile');self.assertEqual(target_platform(),'mobile')
        with self.assertRaises(ValueError):target_platform('desktop')
        with self.assertRaises(ValueError):guard_desktop()
        bind_device('laptop');self.assertEqual(target_platform(),'desktop')
        with self.assertRaises(ValueError):target_platform('mobile')

    def test_payment_browser_title_stops_actions(self):
        with patch('jojo_policy.foreground_title',return_value='Amazon Checkout - Chrome'):
            with self.assertRaises(PermissionError):guard_desktop('scroll')

    def test_only_unambiguous_yes_grants_install(self):
        for text in ['haa kr de','हाँ कर दो','yes']:self.assertTrue(affirmative(text))
        for text in ['nahi','yes but not now','install another app','kal karna']:self.assertFalse(affirmative(text))

    def test_local_desktop_guard_detects_private_fields_not_search_labels(self):
        from jojo_desktop_guard import sensitive_label
        for text in ['Card number','Select payment method','Enter OTP']:
            self.assertTrue(sensitive_label(text))
        self.assertTrue(sensitive_label('Login',password=True))
        self.assertFalse(sensitive_label('Search Amazon.in'))

    def test_native_action_parameters_cannot_inject_intents(self):
        action=validate_action({'type':'open_system','app':'contacts','uri':'tel:123','install_approved':True},'', '')
        self.assertEqual(action,{'type':'open_system','app':'contacts'})
        with self.assertRaises(ValueError):validate_action({'type':'open_system','app':'shell'},'', '')

    def test_store_lookup_failure_does_not_grant_install(self):
        with patch('jojo_mobile_actions.store_app_name',side_effect=ValueError('unverified')):
            with self.assertRaises(ValueError):validate_action({'type':'open','package':'com.unknown.app'},'', '')

class CompanionFlowTests(unittest.TestCase):
    def setUp(self):
        import jojo_android
        self.core=Mock()
        self.core.strip_wake_word=lambda text: text[5:] if text.startswith('JoJo ') else text
        self.core.SLEEP_WORDS={'sleep'};self.core.verify_boss.return_value=True
        app=FastAPI();jojo_android.register(app,self.core);self.api=TestClient(app)
        self.headers={'X-JoJo-Key':'test-key'}
        self.audio=base64.b64encode(b'\x01\x01'*16000).decode()
        self.patches=[patch('jojo_android.pairing_key',return_value='test-key'),patch('jojo_android.record')]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def voice(self,text,session='',device='phone-a'):
        with patch('speech_recognition.Recognizer.recognize_google',return_value=text):
            return self.api.post('/api/mobile/voice',headers=self.headers,json={'audio':self.audio,'session':session,'device_id':device})

    def step(self,session,device='phone-a',**kw):
        return self.api.post('/api/mobile/step',headers=self.headers,json={'session':session,'device_id':device,**kw})

    def install_question(self):
        session=self.voice('JoJo WhatsApp kholo').json()['session']
        with patch('jojo_android.make_client') as factory,patch('jojo_mobile_actions.store_app_name',return_value='WhatsApp Messenger'):
            factory.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'open','package':'com.whatsapp'})
            question=self.step(session,package='com.android.launcher',screen='0: Home').json()
        self.assertIn('install nahi hai',question['reply'])
        return session

    def test_approved_install_resumes_original_goal(self):
        session=self.install_question()
        response=self.voice('haa kr de',session).json()
        self.assertEqual(response['action'],{'type':'open_store','package':'com.whatsapp','name':'WhatsApp Messenger','install_approved':True})

    def test_install_refusal_never_opens_store(self):
        session=self.install_question();result=self.voice('nahi',session).json()
        self.assertEqual(result['action']['type'],'finish');self.assertIn('cancel',result['reply'])

    def test_other_phone_cannot_use_session_or_confirmation(self):
        session=self.install_question()
        self.assertEqual(self.step(session,device='phone-b').status_code,403)
        self.assertEqual(self.voice('haa kr de',session,device='phone-b').json()['state'],'sleeping')

    def test_unverified_yes_never_installs(self):
        session=self.install_question();self.core.verify_boss.return_value=False
        self.assertEqual(self.voice('haan',session).json()['state'],'access_denied')

    def test_payment_observation_never_reaches_model(self):
        session=self.voice('JoJo Amazon kholo').json()['session']
        with patch('jojo_android.make_client') as model:
            result=self.step(session,handoff=True,screen='withheld').json()
        model.assert_not_called();self.assertEqual(result['reply'],PAYMENT_HANDOFF)

    def test_ordinary_shopping_uses_native_mobile_action(self):
        session=self.voice('JoJo Amazon kholo').json()['session']
        with patch('jojo_android.make_client') as model:
            model.return_value.__enter__.return_value.models.generate_content.return_value.text=json.dumps({'type':'open','package':'com.amazon.mShop.android.shopping'})
            result=self.step(session,apps='Amazon = com.amazon.mShop.android.shopping',screen='0: Home').json()
        self.assertEqual(result['action'],{'type':'open','package':'com.amazon.mShop.android.shopping'})

if __name__=='__main__':unittest.main()
