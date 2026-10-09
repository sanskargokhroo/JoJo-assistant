"""Defensive checks use fixtures; never change protection or run a live scan."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from jojo_security import inspect_link, assess, inspect_app_file, security_command
from jojo_policy import require_allowed, guard_tool

def section(*rows):return {'available':True,'data':list(rows)}

class SecurityTests(unittest.TestCase):
    def test_https_is_not_a_clean_bill_of_health(self):
        result=inspect_link('https://example.com')
        self.assertEqual(result['risk'],'unknown')
        self.assertFalse(result['network_contacted'])

    def test_deceptive_userinfo_blocked_without_leaking_password(self):
        result=inspect_link('https://trusted.com:secret@evil.example/login?token=private')
        self.assertEqual(result['host'],'evil.example')
        self.assertEqual(result['risk'],'high')
        self.assertNotIn('secret',str(result));self.assertNotIn('private',str(result))

    def test_expected_domain_boundary(self):
        self.assertEqual(inspect_link('https://paypal.com.evil.example', 'paypal.com')['risk'],'high')
        self.assertNotEqual(inspect_link('https://docs.example.com','example.com')['risk'],'high')

    def test_active_schemes_and_malformed_port(self):
        for value in ['javascript:alert(1)','file:///C:/Windows/test.exe','https://host:bad']:
            self.assertEqual(inspect_link(value)['risk'],'high')

    def test_shortener_download_and_unicode_need_review(self):
        for value in ['https://bit.ly/test','https://example.com/test%2Eexe','https://xn--example-9db.com']:
            self.assertEqual(inspect_link(value)['risk'],'review')

    def test_risky_url_rejected_at_action_boundary(self):
        with self.assertRaises(PermissionError):require_allowed('open https://trusted.com@evil.example')
        guard_tool('inspect_link',{'url':'https://paytm.com'})
        self.assertEqual(inspect_link('https://paytm.com')['risk'],'high')

    def test_unavailable_checks_are_not_safe_results(self):
        result=assess({})
        self.assertIn('defender',result['unknown'])
        self.assertIn('not proof',result['summary'])

    def test_active_threat_distinguished_from_history(self):
        result=assess({'threats':section({'ThreatID':1,'ThreatName':'Fixture threat','IsActive':True},{'ThreatID':2,'IsActive':False})})
        self.assertEqual(len([f for f in result['findings'] if f['level']=='critical']),1)

    def test_firewall_wifi_and_startup_indicators(self):
        result=assess({'firewall':section({'Name':'Public','Enabled':False}), 'wifi':section('Authentication : Open'),
            'startup':section({'Name':'fixture','Encoded':True})})
        findings={f['id']:f for f in result['findings']}
        self.assertEqual(findings['wifi_weak']['level'],'high')
        self.assertEqual(findings['startup:fixture']['level'],'review')
        self.assertIn('legitimate',findings['startup:fixture']['message'])

    def test_local_file_inspection_never_executes_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'fixture.exe';target.write_bytes(b'not executable')
            with patch('jojo_security.probe',return_value={'signature':{'available':True,'data':[{'Status':'NotSigned'}]}}) as probe:
                result=inspect_app_file(str(target))
            self.assertEqual(len(result['sha256']),64)
            self.assertFalse(result['executed']);self.assertFalse(result['uploaded'])
            probe.assert_called_once_with('file',target.resolve())

    def test_wifi_cracking_request_returns_defensive_guidance(self):
        self.assertIn('unauthorized',security_command('wifi hack karna'))

    def test_link_security_command_never_calls_network_probe(self):
        with patch('jojo_security.probe') as probe:
            self.assertIn('Destination',security_command('link check https://trusted.com@evil.example').replace('destination','Destination'))
            probe.assert_not_called()
