import test_00_isolation
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch,Mock
from jojo_dialogue import speech_text,wake_reply
from jojo_controls import disable_startup
from jojo_screen_actions import visible_target

class DesktopExperienceTests(unittest.TestCase):
    def test_emoji_removed_without_damaging_hindi_numbers(self):
        self.assertEqual(speech_text('हाँ 😂 बॉस 👨‍💻 12:30 बजे 👍🏽'), 'हाँ बॉस 12:30 बजे')
        self.assertEqual(speech_text('जींस ₹500 ✅'), 'जींस ₹500')
    def test_no_consecutive_identical_wake_greeting(self):
        previous=wake_reply()
        for _ in range(20):
            current=wake_reply()
            self.assertNotEqual(previous,current)
            previous=current
    def test_current_screen_reference_not_launch(self):
        self.assertEqual(visible_target('isme installed apps ka option hai uss par click kr'),'Installed apps')
        self.assertIsNone(visible_target('installed apps open karo'))
    def test_deactivate_retains_files_and_removes_only_jojo_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);startup=root/'startup';startup.mkdir()
            (startup/'jojo_autostart.vbs').write_text('test')
            (startup/'other.vbs').write_text('keep')
            disable_startup(root,startup)
            self.assertTrue((root/'.no_autostart').exists())
            self.assertFalse((startup/'jojo_autostart.vbs').exists())
            self.assertTrue((startup/'other.vbs').exists())
    def test_dispatch_click_does_not_open_run_or_settings(self):
        import jojo_core as core
        with patch('jojo_screen_actions.click_visible',return_value=(True,'clicked')) as click, patch.object(core,'open_windows_settings') as settings, patch('jojo_policy.guard_desktop'):
            self.assertEqual(core.dispatch_command('isme installed apps par click karo'),'clicked')
            click.assert_called_once_with('Installed apps')
            settings.assert_not_called()
    def test_border_only_render_has_transparent_center(self):
        from jojo_fog import FogRenderer
        image=FogRenderer(800,600).render(1,center=False)
        self.assertEqual(image.getpixel((400,300))[3],0)
    def test_radio_failure_not_reported_as_success(self):
        import jojo_core as core
        with patch.object(core,'control_hardware',return_value=(False,'DeniedByUser')),patch.object(core,'open_windows_settings'):
            self.assertIn('off nahi hua',core.execute_pc_tasks('bluetooth off karo'))

    def test_stale_speech_generation_cannot_restart_audio(self):
        import jojo_core as core
        with patch.object(core,'_speech_epoch',2),patch.object(core,'update_voice_state') as state:
            core._speak_now('old acknowledgement',epoch=1)
            state.assert_not_called()

    @unittest.skipUnless(__import__('os').name=='nt','Windows process matching')
    def test_emergency_exit_only_stops_matching_installation(self):
        import subprocess,sys
        from jojo_controls import terminate_backend
        with tempfile.TemporaryDirectory(prefix='jojo-stop-fixture-') as directory:
            root=Path(directory)
            (root/'jojo_core.py').write_text('import time; time.sleep(30)')
            (root/'other.py').write_text('import time; time.sleep(30)')
            core=subprocess.Popen([sys.executable,str(root/'jojo_core.py')])
            other=subprocess.Popen([sys.executable,str(root/'other.py')])
            try:
                terminate_backend(root)
                core.wait(timeout=5)
                self.assertIsNone(other.poll())
            finally:
                for process in (core,other):
                    if process.poll() is None:process.terminate()
                    process.wait(timeout=5)
