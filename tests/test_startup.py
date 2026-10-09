import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import jojo_start as start
import jojo_usb

class StartupTests(unittest.TestCase):
    def test_install_is_idempotent_and_preserves_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);python=root/'pythonw.exe';python.touch()
            startup=root/'Startup';startup.mkdir();other=startup/'other.vbs';other.write_text('existing')
            target=start.install(startup, root/'JoJo space', python)
            original=target.read_bytes()
            start.install(startup, root/'JoJo space', python)
            self.assertEqual(original,target.read_bytes())
            self.assertEqual(other.read_text(),'existing')
            self.assertIn('--background',target.read_text(encoding='utf-16'))
            self.assertIn('JoJo space',target.read_text(encoding='utf-16'))

    @patch('jojo_usb.subprocess.run')
    def test_reconnect_skips_unauthorized_and_unrelated_devices(self,run):
        def response(args,**kwargs):
            value=''
            if args[1:]==['devices']:value='List of devices attached\na\tunauthorized\nb\tdevice\nc\tdevice\n'
            elif 'path' in args and args[2]=='c':value='package:/data/app/jojo/base.apk'
            return SimpleNamespace(returncode=0,stdout=value)
        run.side_effect=response;jojo_usb.restore('adb')
        calls=[call.args[0] for call in run.call_args_list]
        self.assertIn(['adb','-s','c','reverse','tcp:8000','tcp:8000'],calls)
        self.assertFalse(any('-s' in call and call[2]=='a' for call in calls))
        self.assertFalse(any('reverse' in call and call[2]=='b' for call in calls))

    @patch('jojo_usb.subprocess.run')
    def test_existing_tunnel_is_not_rewritten(self,run):
        run.side_effect=[SimpleNamespace(returncode=0,stdout='List of devices attached\na\tdevice\n'),
                         SimpleNamespace(returncode=0,stdout='package:/app.apk'),
                         SimpleNamespace(returncode=0,stdout='UsbFfs tcp:8000 tcp:8000\n')]
        jojo_usb.restore('adb');self.assertEqual(run.call_count,3)

if __name__=='__main__':unittest.main()
