"""Exercise UIA boundary using fake elements; no real desktop inspection or input."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from jojo_desktop_guard import _inspect

def node(name='',kind='Button',password=False,parent=None):
    return SimpleNamespace(name=name,control_type=kind,element=SimpleNamespace(CurrentIsPassword=password),parent=parent)

class DesktopGuardTests(unittest.TestCase):
    def setUp(self):
        self.api=Mock();self.focus=Mock()
        modules={'pywinauto.uia_element_info':SimpleNamespace(UIAElementInfo=self.api),
                 'pywinauto.uia_defines':SimpleNamespace(IUIA=lambda:SimpleNamespace(get_focused_element=self.focus))}
        p=patch.dict(sys.modules,modules);p.start();self.addCleanup(p.stop)

    def test_click_payment_child_or_parent_is_blocked(self):
        for target in [node('Pay now'),node('icon',parent=node('Buy now')),node('Card number',kind='Edit')]:
            self.api.from_point.return_value=target
            self.assertTrue(_inspect('point',(10,20)))

    def test_search_click_remains_available(self):
        self.api.from_point.return_value=node('Search Amazon.in',kind='Edit')
        self.assertFalse(_inspect('point',(10,20)))

    def test_unlabelled_canvas_cannot_be_clicked_blindly(self):
        self.api.from_point.return_value=node('',kind='Pane',parent=node('Amazon',kind='Document'))
        with self.assertRaises(RuntimeError):_inspect('point',(10,20))

    def test_focused_password_stops_typing(self):
        self.api.return_value=node('Password',kind='Edit',password=True)
        self.assertTrue(_inspect('focus',None))
        self.focus.assert_called_once_with()

    def test_focused_message_input_remains_available(self):
        self.api.return_value=node('Type a message',kind='Edit')
        self.assertFalse(_inspect('focus',None))

if __name__=='__main__':unittest.main()
