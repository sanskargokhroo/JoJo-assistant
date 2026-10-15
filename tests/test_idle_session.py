"""Silence cannot cancel work; manual stop is explicit."""
import test_00_isolation
import unittest
from unittest.mock import patch, Mock
class IdleSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import jojo_core
        cls.core=jojo_core
    def test_silence_never_cancels_even_with_legacy_timeout(self):
        with patch.object(self.core,'SESSION_TIMEOUT',10), patch.object(self.core,'is_active_session',True), patch.object(self.core,'task_manager') as manager:
            self.assertFalse(self.core.expire_idle_session(999999999))
            manager.cancel_pending.assert_not_called()
    def test_manual_sleep_stops_speech_and_only_laptop_work(self):
        with patch.object(self.core,'task_manager') as manager, patch.object(self.core,'stop_speech') as stop, patch.object(self.core,'update_voice_state') as state, patch.object(self.core,'vad_listener',None):
            self.core.pause_session()
            manager.cancel_pending.assert_called_once_with('laptop')
            stop.assert_called_once()
            self.assertFalse(state.call_args.kwargs['active'])
