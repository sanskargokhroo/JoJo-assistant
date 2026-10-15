import test_00_isolation
import unittest
from unittest.mock import Mock, patch


class KeyboardWakeTests(unittest.TestCase):
    def setUp(self):
        import jojo_core
        self.core=jojo_core

    def test_arm_is_not_authentication_and_expires(self):
        c=self.core
        with patch.object(c,'is_active_session',False), patch.object(c,'keyboard_wake_deadline',0), patch.object(c,'vad_listener',None), patch.object(c,'update_voice_state'), patch.object(c,'microphone_paused'), patch.object(c.time,'monotonic',return_value=100):
            self.assertEqual(c.api_keyboard_wake()['status'],'armed')
            self.assertFalse(c.is_active_session)
            self.assertTrue(c.consume_keyboard_wake())
            self.assertFalse(c.consume_keyboard_wake())
            c.api_keyboard_wake()
            with patch.object(c.time,'monotonic',return_value=116):self.assertFalse(c.consume_keyboard_wake())

    def test_shortcut_command_still_requires_voice_match(self):
        c=self.core
        for match in (False,True):
            with self.subTest(match=match), patch.object(c,'is_active_session',False), patch.object(c,'keyboard_wake_deadline',float('inf')), patch.object(c,'shutdown_requested') as shutdown, patch.object(c,'microphone_paused') as mic, patch.object(c,'is_speaking',False), patch.object(c,'listen_command',return_value=('calculator kholo',b'audio')), patch.object(c,'verify_boss',return_value=Mock(is_match=match,similarity=.9)) as verify, patch.object(c,'update_voice_state'), patch.object(c,'stop_speech'), patch.object(c,'speak'), patch.object(c,'task_manager') as manager:
                mic.is_set.return_value=False
                shutdown.is_set.side_effect=[False,True]
                c.run_voice_loop()
                verify.assert_called_once()
                self.assertEqual(manager.submit.call_count,1 if match else 0)

    def test_stop_revokes_pending_keyboard_wake(self):
        c=self.core
        with patch.object(c,'is_active_session',False), patch.object(c,'keyboard_wake_deadline',float('inf')), patch.object(c,'task_manager'), patch.object(c,'stop_speech'), patch.object(c,'update_voice_state'), patch.object(c,'vad_listener',None):
            c.pause_session()
            self.assertFalse(c.consume_keyboard_wake())
