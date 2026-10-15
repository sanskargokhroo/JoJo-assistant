import test_00_isolation
import unittest
from unittest.mock import Mock,patch


class VoiceSessionRecoveryTests(unittest.TestCase):
    def run_command(self,match,initial_speaking=False):
        import jojo_core as c
        def listen(**kwargs):
            c.is_speaking=False
            return 'setting on kr',b'voice'
        with patch.object(c,'is_active_session',True), patch.object(c,'is_speaking',initial_speaking), patch.object(c,'shutdown_requested') as shutdown, patch.object(c,'microphone_paused') as mic, patch.object(c,'listen_command',side_effect=listen), patch.object(c,'verify_boss',return_value=Mock(is_match=match,similarity=.7)) as verify, patch.object(c,'update_voice_state'), patch.object(c,'stop_speech'), patch.object(c,'speak') as speak, patch.object(c,'task_manager') as manager:
            shutdown.is_set.side_effect=[False,True];mic.is_set.return_value=False
            c.run_voice_loop()
            self.assertTrue(c.is_active_session)
            verify.assert_called_once()
            self.assertEqual(manager.submit.call_count,1 if match else 0)
            if not match:speak.assert_called_once()

    def test_failed_match_rejects_command_without_ending_session(self):
        self.run_command(False)

    def test_command_after_speech_finishes_is_not_silently_dropped(self):
        self.run_command(True,initial_speaking=True)

    def test_settings_variants_use_local_handler(self):
        import jojo_core as c
        for text in ['setting on kr','settings open karo','सेटिंग ऑन करो','सेटिंग्स खोलो']:
            with self.subTest(text=text),patch.object(c,'open_windows_settings',return_value=True) as launch:
                result=c.execute_pc_tasks(text,source='laptop')
                launch.assert_called_once_with('')
                self.assertTrue(result)
