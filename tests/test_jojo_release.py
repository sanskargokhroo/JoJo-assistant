import json
import tempfile
from pathlib import Path
import unittest
import zipfile
from jojo_release import files,audit,export

class ReleaseTests(unittest.TestCase):
    def test_private_files_and_history_cannot_enter_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'jojo_example.py').write_text('print("hello")')
            (root/'firebase_key.json').write_text('{}')
            (root/'jojo_account.json').write_text('{"secret":"private"}')
            (root/'jojo_memory.db').write_bytes(b'private memory')
            (root/'README.md').write_text('JoJo')
            selected=files(root)
            self.assertEqual({p.name for p in selected},{'jojo_example.py','README.md'})
            with zipfile.ZipFile(export(selected,root)) as archive:
                self.assertFalse(any('firebase' in p or '.db' in p or 'account' in p or '.git/' in p for p in archive.namelist()))
    def test_secret_check_fails_without_printing_value(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'jojo_example.py'
            secret='AIza'+'x'*35
            path.write_text('key='+repr(secret))
            findings=audit([path],root)
            self.assertTrue(findings);self.assertNotIn(secret,str(findings))
            with self.assertRaises(RuntimeError):export([path],root)
    def test_private_owner_identifier_caught(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'jojo_owner_identity.json').write_text(json.dumps({'name':'Private Fixture Owner'}))
            path=root/'README.md';path.write_text('Welcome Private Fixture Owner')
            self.assertTrue(audit([path],root))
    def test_opaque_google_credentials_are_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'jojo_example.py'
            path.write_text('keys='+repr(['AQ.'+'a'*48]))
            self.assertTrue(audit([path],root))

if __name__=='__main__':unittest.main()
