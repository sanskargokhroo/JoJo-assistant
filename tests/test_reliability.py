"""Regression tests: no real model calls, microphone capture, GUI clicks or shell actions."""
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

_state = tempfile.TemporaryDirectory(prefix='jojo-tests-')
os.environ['JOJO_DATA_DIR'] = _state.name
os.environ['JOJO_DISABLE_CLOUD'] = '1'
os.environ['JOJO_NO_OVERLAY'] = '1'

import numpy as np
from google.genai import types
from jojo_runtime import TaskManager, checkpoint, needs_planning, is_stop_command
from jojo_audio import SpeechSegmenter, MicrophoneListener
from jojo_agent_loop import run_tool_loop

def response(*calls, text=None):
    parts = [types.Part(function_call=types.FunctionCall(name=name, args=args, id=f'call{i}')) for i, (name, args) in enumerate(calls)]
    if text is not None:
        parts.append(types.Part.from_text(text=text))
    return SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role='model', parts=parts))], text=text)

class RoutingTests(unittest.TestCase):
    def test_compound_requests_reach_planner(self):
        for text in ('notepad kholo aur hello likho', 'open chrome then search python', 'नोटपैड खोलकर उसमें लिखो', 'write and save a file', 'notepad me hello type karo'):
            self.assertTrue(needs_planning(text), text)

    def test_simple_commands_stay_local(self):
        self.assertFalse(needs_planning('volume kam karo'))
        self.assertFalse(needs_planning('open calculator'))

    def test_stop_does_not_match_desktop(self):
        for text in ('open desktop', 'make stopwatch', 'stopwatch kholo'):
            self.assertFalse(is_stop_command(text))
        self.assertTrue(is_stop_command('JoJo stop!'))

class QueueTests(unittest.TestCase):
    def wait(self, manager, id):
        self.assertTrue(manager.tasks[id].done.wait(3))
        return manager.get(id)

    def test_tasks_execute_serially(self):
        running = 0
        peak = 0
        guard = threading.Lock()
        def handler(message, source):
            nonlocal running, peak
            with guard:
                running += 1
                peak = max(peak, running)
            time.sleep(.01)
            with guard:
                running -= 1
            return message
        manager = TaskManager(handler)
        tasks = [manager.submit(str(i)) for i in range(5)]
        for task in tasks:
            self.assertEqual(self.wait(manager, task['id'])['status'], 'completed')
        self.assertEqual(peak, 1)

    def test_failure_does_not_kill_worker(self):
        def handler(message, source):
            if message == 'bad':
                raise RuntimeError('test failure')
            return 'ok'
        manager = TaskManager(handler)
        first, second = manager.submit('bad'), manager.submit('good')
        self.assertEqual(self.wait(manager, first['id'])['status'], 'failed')
        self.assertEqual(self.wait(manager, second['id'])['reply'], 'ok')

    def test_cancel_stops_before_next_action(self):
        entered, release = threading.Event(), threading.Event()
        actions = []
        def handler(message, source):
            actions.append('first')
            entered.set()
            release.wait(2)
            checkpoint()
            actions.append('second')
            return 'done'
        manager = TaskManager(handler)
        task = manager.submit('work')
        self.assertTrue(entered.wait(1))
        manager.cancel_task(task['id'])
        release.set()
        self.assertEqual(self.wait(manager, task['id'])['status'], 'cancelled')
        self.assertEqual(actions, ['first'])

    def test_cancel_queued_task_does_not_execute(self):
        release, entered = threading.Event(), threading.Event()
        actions = []
        def handler(message, source):
            entered.set()
            release.wait(2)
            actions.append(message)
            return message
        manager = TaskManager(handler)
        first = manager.submit('first')
        self.assertTrue(entered.wait(1))
        second = manager.submit('second')
        manager.cancel_task(second['id'])
        release.set()
        self.wait(manager, first['id'])
        self.assertEqual(self.wait(manager, second['id'])['status'], 'cancelled')
        self.assertEqual(actions, ['first'])

    def test_empty_result_is_not_success(self):
        manager = TaskManager(lambda *_: None)
        task = manager.submit('work')
        self.assertEqual(self.wait(manager, task['id'])['status'], 'incomplete')

    def test_queue_is_bounded(self):
        gate, started = threading.Event(), threading.Event()
        def handler(*_):
            started.set()
            gate.wait(2)
            return 'ok'
        manager = TaskManager(handler, max_pending=1)
        manager.submit('first')
        self.assertTrue(started.wait(1))
        manager.submit('second')
        with self.assertRaises(queue.Full):
            manager.submit('third')
        gate.set()

    def test_shutdown_rejects_new_work(self):
        manager = TaskManager(lambda *_: 'ok')
        manager.stop_all()
        with self.assertRaises(ValueError):
            manager.submit('new work')

class AudioTests(unittest.TestCase):
    def tone(self, n=800):
        return np.full(n, 1200, dtype=np.int16)

    def test_long_sentence_is_not_cut_at_seven_seconds(self):
        segmenter = SpeechSegmenter()
        for _ in range(240):  # Twelve seconds, without wall-clock sleeps.
            self.assertIsNone(segmenter.feed(self.tone()))
        result = None
        for _ in range(22):
            result = segmenter.feed(np.zeros(800, dtype=np.int16))
        self.assertIsNotNone(result)
        self.assertEqual(np.count_nonzero(result), 240*800)  # Onset isn't duplicated.

    def test_short_pause_does_not_end_sentence(self):
        s = SpeechSegmenter()
        for _ in range(12):
            s.feed(self.tone())
        for _ in range(12):
            self.assertIsNone(s.feed(np.zeros(800, dtype=np.int16)))
        self.assertIsNone(s.feed(self.tone()))

    def test_maximum_sentence_is_bounded(self):
        s = SpeechSegmenter(max_seconds=2)
        results = [s.feed(self.tone()) for _ in range(40)]
        self.assertIsNotNone(results[-1])
        self.assertEqual(len(results[-1]), 32000)

    def test_silence_and_single_click_do_not_trigger(self):
        s = SpeechSegmenter()
        for _ in range(30):
            self.assertIsNone(s.feed(np.zeros(800, dtype=np.int16)))
        s.feed(self.tone())
        for _ in range(30):
            self.assertIsNone(s.feed(np.zeros(800, dtype=np.int16)))

    def test_audio_queue_drops_oldest(self):
        listener = MicrophoneListener()
        for i in range(80):
            listener._callback(np.full((800, 1), i, dtype=np.int16), 800, None, None)
        self.assertEqual(listener.q.qsize(), 64)
        self.assertEqual(listener.q.get()[1][0], 16)

    def test_self_speech_is_not_buffered(self):
        listener = MicrophoneListener(suppressed=lambda: True)
        listener._callback(np.ones((800, 1), dtype=np.int16), 800, None, None)
        self.assertTrue(listener.q.empty())

class AgentTests(unittest.TestCase):
    def client(self, responses):
        return SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=responses)))

    def test_executes_and_requires_evidence(self):
        actions = []
        def write_note(text: str):
            actions.append(text)
            return 'saved'
        client = self.client([response(('write_note', {'text': 'hello'})),
            response(('finish_task', {'summary': 'Saved hello', 'evidence_steps': [1]}))])
        result = run_tool_loop(client, 'save hello', '', [write_note])
        self.assertEqual(result.status, 'completed')
        self.assertEqual(actions, ['hello'])
        submitted = client.models.generate_content.call_args.kwargs['contents']
        tool_response = submitted[2].parts[0].function_response
        self.assertEqual(tool_response.response['evidence_step'], 1)

    def test_text_claim_is_not_completion(self):
        result = run_tool_loop(self.client([response(text='Done!'), response(text='Done!')]), 'write a file', '', [])
        self.assertEqual(result.status, 'incomplete')

    def test_empty_response_is_not_completion(self):
        result = run_tool_loop(self.client([response()]), 'work', '', [])
        self.assertEqual(result.status, 'incomplete')

    def test_missing_evidence_rejected(self):
        result = run_tool_loop(self.client([
            response(('finish_task', {'summary': 'done', 'evidence_steps': [9]})),
            response(('finish_task', {'summary': 'Need a filename', 'evidence_steps': [], 'status': 'needs_input'}))]), 'work', '', [])
        self.assertEqual(result.status, 'needs_input')

    def test_failed_tool_cannot_be_completion_evidence(self):
        def fail():
            return {'error': 'denied'}
        result = run_tool_loop(self.client([response(('fail', {})),
            response(('finish_task', {'summary': 'done', 'evidence_steps': [1]})),
            response(('finish_task', {'summary': 'Could not write', 'evidence_steps': [], 'status': 'incomplete'}))]), 'work', '', [fail])
        self.assertEqual(result.status, 'incomplete')

    def test_transient_model_retry_does_not_repeat_action(self):
        calls = []
        def work():
            calls.append(1)
            return 'ok'
        client = self.client([response(('work', {})), TimeoutError(),
            response(('finish_task', {'summary': 'done', 'evidence_steps': [1]}))])
        with patch('jojo_agent_loop.time.sleep'):
            result = run_tool_loop(client, 'work', '', [work])
        self.assertEqual(result.status, 'completed')
        self.assertEqual(calls, [1])

    def test_tool_error_is_given_back_for_recovery(self):
        def fail():
            raise ValueError('invalid path')
        result = run_tool_loop(self.client([response(('fail', {})),
            response(('finish_task', {'summary': 'Missing path', 'status': 'needs_input', 'evidence_steps': []}))]), 'work', '', [fail])
        self.assertFalse(result.steps[0]['ok'])
        self.assertEqual(result.status, 'needs_input')

    def test_step_budget_bounds_parallel_tool_calls(self):
        called = []
        def work():
            called.append(1)
            return 'ok'
        result = run_tool_loop(self.client([response(*[('work', {})]*5)]), 'work', '', [work], max_steps=2)
        self.assertEqual(result.status, 'incomplete')
        self.assertEqual(len(called), 2)

    def test_actual_file_workflow_preserves_both_steps(self):
        target = Path(_state.name) / 'workflow-note.txt'
        def write_note(content: str):
            target.write_text(content, encoding='utf-8')
            return 'written'
        def read_note():
            return target.read_text(encoding='utf-8')
        result = run_tool_loop(self.client([
            response(('write_note', {'content': 'Hello JoJo'})),
            response(('read_note', {})),
            response(('finish_task', {'summary': 'Written and verified', 'evidence_steps': [2]}))
        ]), 'write a note then verify it', '', [write_note, read_note])
        self.assertEqual(result.status, 'completed')
        self.assertEqual([step['tool'] for step in result.steps], ['write_note', 'read_note'])
        self.assertEqual(target.read_text(encoding='utf-8'), 'Hello JoJo')

class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import jojo_core
        cls.core = jojo_core
        from fastapi.testclient import TestClient
        cls.api = TestClient(jojo_core.app)

    def test_core_import_does_not_start_services(self):
        self.assertFalse(any(t.name in ('JoJo API', 'JoJo reminders', 'JoJo cloud') for t in threading.enumerate()))

    def test_compound_task_bypasses_first_action_handler(self):
        with patch.object(self.core, 'execute_pc_tasks') as reflex, patch.object(self.core.jojo_agi, 'run_agent_cycle', return_value='all done') as agent:
            result = self.core.dispatch_command('notepad kholo aur hello likho')
        reflex.assert_not_called()
        agent.assert_called_once()
        self.assertEqual(result, 'all done')

    def test_explanation_does_not_open_an_app(self):
        with patch.object(self.core, 'execute_pc_tasks') as reflex, patch.object(self.core, 'ask_jojo_brain', return_value='Explanation'):
            result = self.core.dispatch_command('what is notepad')
        reflex.assert_not_called()
        self.assertEqual(result, 'Explanation')

    def test_empty_chat_response_has_bounded_retries(self):
        fake = Mock()
        fake.chats.create.return_value.send_message.return_value.text = ''
        with patch.object(self.core, 'make_client', return_value=fake), \
             patch.object(self.core, 'GEMINI_KEYS', ['test-key']), \
             patch.object(self.core, 'current_gemini_index', 0), \
             patch.object(self.core.jojo_agi, 'process_emotional_context', return_value={}), \
             patch.object(self.core.jojo_agi, 'build_eq_context_string', return_value=''), \
             patch.object(self.core, 'check_and_learn_skills', return_value=None), \
             patch.object(self.core, 'check_learned_skill_trigger', return_value=None), \
             patch.object(self.core, 'search_cached_memory', return_value=None), \
             patch.object(self.core, 'get_user_facts', return_value={}):
            result = self.core.ask_jojo_brain('explain rainbows')
        self.assertEqual(fake.chats.create.return_value.send_message.call_count, 1)
        fake.close.assert_called_once()
        self.assertIn('complete nahi hua', result)

    def test_api_task_submission_is_nonblocking(self):
        release = threading.Event()
        manager = TaskManager(lambda *_: release.wait(2) and 'done')
        with patch.object(self.core, 'task_manager', manager):
            res = self.api.post('/api/tasks', json={'message': 'work', 'speak': False})
            self.assertEqual(res.status_code, 200)
            self.assertIn(res.json()['status'], ('queued', 'running'))
            status = self.api.get('/api/tasks/' + res.json()['id'])
            self.assertEqual(status.status_code, 200)
            release.set()

    def test_missing_audio_never_claims_verified(self):
        res = self.api.post('/api/verify_voice', json={})
        self.assertFalse(res.json()['verified'])

    def test_state_has_compatible_field_names(self):
        self.core.update_voice_state(transcript='hello', reply='hi')
        state = self.api.get('/api/voice_state').json()
        self.assertEqual(state['transcript'], state['last_transcript'])
        self.assertEqual(state['reply'], state['last_reply'])

    def test_wake_word_only_removed_from_prefix(self):
        self.assertEqual(self.core.strip_wake_word('JoJo open JoJo notes'), 'open JoJo notes')
        self.assertEqual(self.core.strip_wake_word('jojobar file'), 'jojobar file')

    def test_empty_task_rejected(self):
        self.assertEqual(self.api.post('/api/tasks', json={'message': '  '}).status_code, 400)

    def test_untrusted_website_cannot_submit_commands(self):
        result = self.api.post('/api/tasks', json={'message': 'work'}, headers={'Origin': 'https://untrusted.example'})
        self.assertEqual(result.status_code, 403)

    def test_device_change_restarts_capture(self):
        fake = Mock()
        with patch.object(self.core, 'vad_listener', fake):
            res = self.api.post('/api/config', json={'audio_device_id': -1})
            self.assertEqual(res.status_code, 200)
            fake.close.assert_called_once()
            self.assertIsNone(fake.device)

    def test_failed_brightness_does_not_claim_success(self):
        with patch.object(self.core, 'get_laptop_brightness', return_value=50), patch.object(self.core, 'set_laptop_brightness', return_value=False):
            reply = self.core.execute_pc_tasks('brightness badhao', source='laptop')
            self.assertIn('could not be confirmed', reply)

    def test_unknown_radio_state_is_not_reported_off(self):
        with patch.object(self.core, 'control_hardware', return_value=(False, 'No radio found')):
            for text in ('bluetooth status', 'wifi status'):
                self.assertIn('Could not read', self.core.execute_pc_tasks(text, source='laptop'))

    def test_failed_radio_enable_is_not_success(self):
        with patch.object(self.core, 'control_hardware', return_value=(False, 'Denied')):
            for text in ('bluetooth', 'wifi'):
                self.assertIn('could not be enabled', self.core.execute_pc_tasks(text, source='laptop'))

if __name__ == '__main__':
    unittest.main()
