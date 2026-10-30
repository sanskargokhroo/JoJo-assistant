import unittest
from jojo_mobile_commands import navigation,sleep_requested,planning_failure
class CommandTests(unittest.TestCase):
    def test_open_aliases(self):
        for text,expected in [('album kholo','gallery'),('gallery open karo','gallery'),('एसएमएस खोलो','messages'),('सेटिंग ऑन करो','settings'),('open contacts','contacts')]:
            self.assertEqual(navigation(text),expected)
    def test_compound_and_toggle_not_misrouted(self):
        for text in ['gallery kholo aur photo send karo','sms bhejo','bluetooth off karo','settings mein wifi on karo']:
            self.assertIsNone(navigation(text))
    def test_sleep_is_assistant_only(self):
        for text in ['thik hai off ho jao','ठीक है बंद हो जाओ','okay go to sleep']:
            self.assertTrue(sleep_requested(text))
        for text in ['bluetooth off ho jao','phone band karo','screen off karo']:
            self.assertFalse(sleep_requested(text))
    def test_timeout_explained_without_leaking_payload(self):
        error=RuntimeError('secret prompt');error.code=504
        self.assertIn('time par',planning_failure(error))
        self.assertNotIn('secret',planning_failure(error))
