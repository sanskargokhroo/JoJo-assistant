import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from jojo_start import install_launch_shortcut
from jojo_controls import disable_startup


class LaunchShortcutTests(unittest.TestCase):
    def test_launch_is_separate_from_login_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'JoJo space';root.mkdir()
            python=root/'python.exe';python.with_name('pythonw.exe').touch()
            programs=Path(directory)/'Programs'
            with patch('jojo_start.subprocess.run') as run:
                link=install_launch_shortcut(root,python,programs)
            env=run.call_args.kwargs['env']
            self.assertIn('--no-autostart',env['JOJO_LINK_ARGS'])
            self.assertIn(str(root.resolve()/'jojo_start.py'),env['JOJO_LINK_ARGS'])
            self.assertIn("$link.Hotkey='CTRL+ALT+J'",run.call_args.args[0][-1])
            link.parent.mkdir(parents=True);link.touch()
            startup=programs/'Startup';startup.mkdir()
            (startup/'jojo_autostart.vbs').touch()
            disable_startup(root,startup)
            self.assertTrue(link.exists())
            self.assertTrue((root/'.no_autostart').exists())
            self.assertFalse((startup/'jojo_autostart.vbs').exists())
