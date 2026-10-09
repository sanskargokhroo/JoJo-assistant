import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import jojo_user_config as config

class SetupTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_credentials_roundtrip_and_no_plaintext_key_on_disk(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(config,'private_dir',return_value=Path(temp)):
            path=config.save('openai','fixture-model','fixture-secret-value',owner_name='Fixture Owner')
            self.assertNotIn('fixture-secret-value',path.read_text())
            self.assertEqual(config.load()['api_key'],'fixture-secret-value')
            self.assertEqual(config.owner()['name'],'Fixture Owner')
    def test_firebase_web_config_is_not_service_account(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'config.json';file.write_text('{"apiKey":"fixture"}')
            with self.assertRaisesRegex(ValueError,'service-account'):
                config.save('gemini','fixture','fixture',str(file),'Owner')
    def test_capability_off_is_enforced_before_tool(self):
        import jojo_capabilities as capabilities
        from jojo_policy import guard_tool
        with patch.object(capabilities,'read_preferences',return_value={'capabilities':{'web':False}}):
            self.assertFalse(capabilities.allowed_tool('check_live_weather'))
            with self.assertRaises(PermissionError):guard_tool('check_live_weather',{'location':'Delhi'})

if __name__=='__main__':unittest.main()
