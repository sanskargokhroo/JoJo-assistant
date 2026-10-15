import test_00_isolation
import unittest
from unittest.mock import patch


class SelectedVoiceTests(unittest.TestCase):
    def test_cache_identity_includes_delivery_settings(self):
        import jojo_core as c
        original=c.speech_cache_key('hello')
        for setting,value in [('voice','other'),('rate','+0%'),('pitch','+0Hz')]:
            with patch.dict(c.VOICE_PARAMS,{setting:value}):
                self.assertNotEqual(original,c.speech_cache_key('hello'))
        self.assertEqual(original,c.speech_cache_key(' hello '))

    def test_failed_selected_voice_does_not_launch_another_engine(self):
        import jojo_core as c
        with patch('jojo_workspace.private_session',return_value=False), patch.object(c,'get_cached_speech_path',return_value=None), patch.object(c,'synthesize_sync',return_value=False), patch.object(c,'update_voice_state'), patch.object(c,'report_audio_error') as report, patch.object(c.subprocess,'Popen') as process:
            c._speak_now('Test selected voice')
            process.assert_not_called()
            report.assert_called_once()
