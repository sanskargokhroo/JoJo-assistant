import threading
import test_00_isolation
import unittest
from unittest.mock import patch
from jojo_runtime import TaskManager, wait_for_model
from jojo_navigation import shopping_navigation

class TrialRegressionTests(unittest.TestCase):
    def test_exact_search_and_single_homepage_route(self):
        self.assertEqual(shopping_navigation('new tab mai amazon open karo')[2], 'https://www.amazon.in')
        self.assertEqual(shopping_navigation('amazon par blue jeans search kr')[1], 'blue jeans')
        self.assertEqual(shopping_navigation('jeans search karo')[2], 'https://www.amazon.in/s?k=jeans')
        self.assertIsNone(shopping_navigation('amazon open karo phir order karo'))
        self.assertIsNone(shopping_navigation('what is amazon'))

    def test_cancel_abandons_model_and_drops_queued_work(self):
        started, release = threading.Event(), threading.Event()
        executed=[]
        def handler(message, source):
            executed.append(message)
            if message=='old':
                def model():
                    started.set()
                    release.wait(5)
                    return 'stale'
                return wait_for_model(model)
            return message
        manager=TaskManager(handler)
        try:
            first=manager.submit('old')
            self.assertTrue(started.wait(2))
            second=manager.submit('queued')
            manager.cancel_pending()
            self.assertTrue(manager.tasks[first['id']].done.wait(1))
            self.assertEqual(manager.get(first['id'])['status'],'cancelled')
            self.assertEqual(manager.get(second['id'])['status'],'cancelled')
            new=manager.submit('new')
            self.assertTrue(manager.tasks[new['id']].done.wait(1))
            self.assertEqual(executed,['old','new'])
        finally:release.set()

    def test_replacement_stops_old_reply_but_keeps_other_device(self):
        entered, release=threading.Event(),threading.Event()
        spoken=[]
        def handler(message, source):
            if message=='old':
                return wait_for_model(lambda: (entered.set(), release.wait(5), 'old')[2])
            return message
        manager=TaskManager(handler,speaker=spoken.append)
        try:
            old=manager.submit('old',speak=True)
            self.assertTrue(entered.wait(2))
            mobile=manager.submit('mobile task',source='mobile')
            new=manager.submit('new',speak=True,replace_pending=True)
            self.assertTrue(manager.tasks[new['id']].done.wait(2))
            self.assertEqual(manager.get(old['id'])['status'],'cancelled')
            self.assertEqual(manager.get(mobile['id'])['status'],'completed')
            self.assertNotIn('old',spoken)
        finally:release.set()

    def test_simple_shopping_dispatch_opens_once_without_agent(self):
        import jojo_core as core
        with patch.object(core,'open_url_in_chrome') as opened, patch.object(core.jojo_agi,'run_agent_cycle') as agent, patch('jojo_policy.guard_desktop'):
            core.dispatch_command('new tab mai amazon open karo')
            opened.assert_called_once_with('https://www.amazon.in')
            agent.assert_not_called()
