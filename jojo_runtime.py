"""A single bounded task queue shared by voice and desktop commands.

Cancellation is cooperative: it prevents the next action. An OS action that has
already started is not rolled back. No task is automatically replayed.
"""
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass, field
import copy
import queue
import re
import threading
import time
import uuid

_context = ContextVar('jojo_task_context', default=None)
_device = ContextVar('jojo_device', default='laptop')

def current_task():
    return _context.get()

def bind_device(source):
    if source not in ('laptop', 'mobile'):
        raise ValueError('Unknown target device')
    _device.set(source)

def target_platform(requested='auto'):
    expected = 'mobile' if _device.get() == 'mobile' else 'desktop'
    if requested not in ('auto', expected):
        raise ValueError('Target mismatch: this task belongs to ' + expected)
    return expected
TERMINAL = {'completed', 'failed', 'cancelled', 'incomplete', 'needs_input'}

class TaskCancelled(Exception):
    pass

def checkpoint():
    task = _context.get()
    if task and task.cancel.is_set():
        raise TaskCancelled('Task stopped. Already executed actions were not undone.')
    if task and time.monotonic() > task.deadline:
        raise TimeoutError('Task time limit reached; unfinished work was not replayed.')

def report_progress(message, tool=None):
    checkpoint()
    task = _context.get()
    if task:
        with task.lock:
            task.progress = message
            task.events.append({'time': time.time(), 'message': message, 'tool': tool})
        if task.persist:
            task.persist(task)

def set_outcome(status):
    task = _context.get()
    if task and status in TERMINAL:
        with task.lock:
            task.outcome = status

def normalize_command(text):
    return re.sub(r'\s+', ' ', text.casefold()).strip(' .!?।')

def is_stop_command(text):
    return normalize_command(text) in {
        'stop', 'cancel', 'cancel task', 'stop task', 'jojo stop', 'jojo cancel',
        'ruk jao', 'ruk ja', 'band karo', 'रुक जाओ', 'जोजो रुक जाओ', 'कैंसल करो',
    }

def needs_planning(text):
    """Keep compound instructions away from single-action substring handlers."""
    value = normalize_command(text)
    if re.search(r'^(?:nahi[, ]|nahin[, ]|no[, ]|correction:|usi ko\b|usko\b|pichhli\b|previous\b)',value):return True
    return bool(re.search(
        r'\b(and|then|aur|phir|fir|uske baad|karke|kholke|usme|usmein)\b|और|फिर|उसके बाद|करके|उसमें|खोलकर', value
    )) or bool(re.search(r'\b(type|write|save|likh|paste|create|rename|move|copy|delete)\b|लिख|सेव|बनाओ', value))

def is_explanation_request(text):
    """Questions about an action must not accidentally perform that action."""
    value = normalize_command(text)
    return bool(re.search(r'^(what is|what are|why|explain|how does|how do|how to)\b', value)
                or re.search(r'\b(kya hai|kya hota hai|kaise kaam|kaise karte|kaise krte)\b', value)
                or re.search(r'क्या है|कैसे काम|क्यों|कैसे करते', value))

@dataclass
class Task:
    id: str
    message: str
    source: str
    speak: bool
    private: bool = False
    persist: object = None
    status: str = 'queued'
    progress: str = 'Waiting'
    reply: str = ''
    error: str = ''
    created_at: float = field(default_factory=time.time)
    deadline: float = 0
    outcome: str = 'completed'
    events: deque = field(default_factory=lambda: deque(maxlen=80))
    done: threading.Event = field(default_factory=threading.Event)
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def snapshot(self):
        with self.lock:
            return {key: copy.deepcopy(getattr(self, key)) for key in (
                'id', 'message', 'source', 'speak', 'private', 'status', 'progress', 'reply', 'error', 'created_at'
            )} | {'events': list(self.events)}

class TaskManager:
    def __init__(self, handler, speaker=None, max_pending=8, task_seconds=300, journal=None):
        self.handler, self.speaker = handler, speaker
        self.journal = journal
        self.task_seconds = task_seconds
        self.queue = queue.Queue(maxsize=max_pending)
        self.tasks = {}
        self.lock = threading.RLock()
        self.active_id = None
        self.worker = None
        self.closed = False

    def submit(self, message, source='laptop', speak=False):
        message = message.strip()
        if not message or len(message) > 12000:
            raise ValueError('Command must contain 1 to 12000 characters.')
        if source not in ('laptop', 'mobile'):
            raise ValueError('Unknown device source.')
        from jojo_config import read_preferences
        task = Task(uuid.uuid4().hex, message, source, speak,
                    private=bool(read_preferences().get('private_session', False)), persist=self._remember)
        with self.lock:
            if self.closed:
                raise ValueError('JoJo is shutting down; no new task was started.')
            self.queue.put_nowait(task)
            self.tasks[task.id] = task
            self._remember(task)
            # Keep recent results without an unbounded in-memory history.
            for old_id, old in list(self.tasks.items()):
                if len(self.tasks) <= 100:
                    break
                if old.done.is_set():
                    del self.tasks[old_id]
            if self.worker is None or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._run, name='JoJo tasks', daemon=True)
                self.worker.start()
        return task.snapshot()

    def stop_all(self):
        """Stop active and queued work before shutdown, without replaying anything."""
        with self.lock:
            self.closed = True
            for task_id in list(self.tasks):
                self.cancel_task(task_id)

    def get(self, task_id):
        with self.lock:
            task = self.tasks.get(task_id)
        return task.snapshot() if task else None

    def cancel_task(self, task_id=None):
        with self.lock:
            task = self.tasks.get(task_id or self.active_id)
            if not task:
                return None
            with task.lock:
                if task.status not in TERMINAL:
                    task.cancel.set()
                    task.progress = 'Stopping after the current action…'
                    if task.status == 'queued':
                        task.status, task.reply = 'cancelled', 'Cancelled before starting.'
                        self._remember(task)
                        task.done.set()
            return task.snapshot()

    def run_sync(self, message, source='laptop'):
        result = self.submit(message, source)
        with self.lock:
            task = self.tasks[result['id']]
        if not task.done.wait(self.task_seconds + 35):
            self.cancel_task(task.id)
            return 'Task is stopping after its current action. Check task status before retrying.'
        return task.reply or task.error

    def _remember(self, task):
        if self.journal and not task.private:
            try:
                self.journal(task.snapshot())
            except Exception as exc:
                task.events.append({'time': time.time(), 'message': 'Memory save failed: ' + type(exc).__name__, 'tool': None})

    def _run(self):
        while True:
            task = self.queue.get()
            try:
                if task.cancel.is_set():
                    continue
                with self.lock:
                    self.active_id = task.id
                with task.lock:
                    task.status, task.progress = 'running', 'Understanding request…'
                    task.deadline = time.monotonic() + self.task_seconds
                self._remember(task)
                token = _context.set(task)
                try:
                    checkpoint()
                    reply = self.handler(task.message, task.source)
                    checkpoint()
                    with task.lock:
                        task.reply = str(reply or 'No result received; completion could not be confirmed.')
                        task.status = task.outcome if reply else 'incomplete'
                        task.progress = task.status.replace('_', ' ').capitalize()
                except TaskCancelled as exc:
                    with task.lock:
                        task.status, task.reply = 'cancelled', str(exc)
                except Exception as exc:
                    with task.lock:
                        task.status, task.error = 'failed', f'{type(exc).__name__}: {exc}'
                        task.reply = 'Kaam poora nahi hua. ' + task.error
                finally:
                    _context.reset(token)
                    self._remember(task)
                    task.done.set()
                if task.speak and self.speaker and not task.cancel.is_set():
                    speech_token = _context.set(task)
                    try:
                        self.speaker(task.reply)
                    except Exception:
                        pass  # Voice failure must not discard the visible task result.
                    finally:
                        _context.reset(speech_token)
            finally:
                with self.lock:
                    self.active_id = None
                self.queue.task_done()
