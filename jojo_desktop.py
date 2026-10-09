"""Native JoJo desktop interface: Tk widgets, no browser or embedded webpage."""
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import urllib.error
import urllib.request
from jojo_instance import claim_instance
from jojo_ambient import AmbientOverlay

ROOT = Path(__file__).resolve().parent
BG, PANEL, TEXT, MUTED, ACCENT = '#0b101c', '#131d2e', '#e7edf8', '#94a4bb', '#55dfcc'
TERMINAL = {'completed', 'failed', 'cancelled', 'incomplete', 'needs_input'}

def request(path, data=None, timeout=2):
    req = urllib.request.Request('http://127.0.0.1:8000' + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

def start_core():
    (ROOT / 'logs').mkdir(exist_ok=True)
    env = dict(os.environ, JOJO_NO_OVERLAY='1', PYTHONUTF8='1', PYTHONUNBUFFERED='1')
    python = Path(sys.executable).with_name('python.exe')
    with open(ROOT / 'logs' / 'core.log', 'a', encoding='utf-8') as log:
        return subprocess.Popen([str(python if python.exists() else sys.executable), '-u', str(ROOT / 'jojo_core.py')],
            cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

class JoJoDesktop:
    def __init__(self, root, launch_core=False, preview=False):
        self.root, self.launch_core = root, launch_core
        self.events, self.requests = queue.Queue(), queue.Queue()
        self.closed = threading.Event()
        self.connected, self.mic_paused = False, False
        self.stopping = False
        self.setup_shown = False
        self.phase, self.activity = 0, 'idle'
        self.last_transcript = self.last_reply = ''
        self.seen = set()
        self.initial_state = True
        self.last_security_alert = ''
        self.last_security_scan = 'idle'
        self.microphones = {'Windows default': -1}
        self.audio_device_id, self.speech_language = -1, 'hi-IN'
        self.barge_in_enabled=False
        root.title('JoJo Desktop')
        root.configure(bg=BG)
        root.geometry('580x780')
        root.minsize(500, 650)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.build()
        self.ambient = AmbientOverlay(root)
        self.append('JoJo', 'Namaste! Boliye “JoJo” ya neeche apna kaam likhiye. Task ki progress yahin dikhegi.')
        root.after(50, self.animate)
        root.after(80, self.drain_events)
        if preview:
            self.connection.set('DESKTOP PREVIEW')
            self.status.set('Ready when you are')
            self.detail.set('Voice • Text • Task progress')
        else:
            threading.Thread(target=self.network_loop, daemon=True, name='JoJo desktop connection').start()

    def button(self, parent, text, command, accent=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if accent else PANEL,
            fg=BG if accent else TEXT, activebackground='#74ecd9' if accent else '#25364e',
            relief='flat', bd=0, padx=14, pady=9, font=('Segoe UI', 10), cursor='hand2')

    def build(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill='x', padx=24, pady=(22, 0))
        tk.Label(head, text='JOJO', font=('Segoe UI', 23, 'bold'), fg=TEXT, bg=BG).pack(side='left')
        self.connection = tk.StringVar(value='STARTING…')
        tk.Label(head, textvariable=self.connection, font=('Segoe UI', 9, 'bold'), fg=ACCENT, bg=BG).pack(side='right')
        self.canvas = tk.Canvas(self.root, width=280, height=136, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(4, 0))
        self.status = tk.StringVar(value='Connecting to your assistant…')
        tk.Label(self.root, textvariable=self.status, bg=BG, fg=TEXT, font=('Segoe UI', 15, 'bold')).pack()
        self.detail = tk.StringVar(value='Your conversation and controls stay in this desktop window.')
        tk.Label(self.root, textvariable=self.detail, bg=BG, fg=MUTED, wraplength=480,
            font=('Segoe UI', 10)).pack(padx=20, pady=(7, 14))
        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill='x', padx=24)
        self.mic_button = self.button(controls, 'Pause mic', self.toggle_mic)
        self.mic_button.pack(side='left')
        self.button(controls, 'Stop task', self.stop).pack(side='left', padx=8)
        self.button(controls, 'Settings', self.settings).pack(side='right')
        lifecycle = tk.Frame(self.root, bg=BG)
        lifecycle.pack(fill='x', padx=24, pady=(8,0))
        self.button(lifecycle, 'Stop JoJo', self.stop_assistant).pack(side='left')
        self.button(lifecycle, 'Uninstall JoJo', self.uninstall).pack(side='right')
        setup_controls=tk.Frame(self.root,bg=BG);setup_controls.pack(fill='x',padx=24,pady=(8,0))
        self.button(setup_controls,'Owner setup',self.owner_setup).pack(side='left')
        from jojo_workspace_ui import open_workspace
        self.button(setup_controls,'Workspace',lambda:open_workspace(self.root,request)).pack(side='left',padx=6)
        self.button(setup_controls,'Skills & plugins',self.skills).pack(side='right')
        security_controls = tk.Frame(self.root, bg=BG)
        security_controls.pack(fill='x', padx=24, pady=(8,0))
        self.button(security_controls, 'Security check', lambda: self.requests.put(('submit','/api/tasks',{'message':'security check','source':'laptop','speak':False}))).pack(side='left')
        self.button(security_controls, 'Defender quick scan', lambda: self.requests.put(('security_scan','/api/security/quick_scan',{}))).pack(side='right')
        self.chat = ScrolledText(self.root, bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief='flat', borderwidth=0, font=('Segoe UI', 11), wrap='word', padx=16, pady=12,
            state='disabled', height=10)
        self.chat.pack(fill='both', expand=True, padx=24, pady=14)
        self.chat.tag_configure('name', foreground=ACCENT, font=('Segoe UI', 10, 'bold'))
        composer = tk.Frame(self.root, bg=PANEL, padx=10, pady=10)
        composer.pack(fill='x', padx=24)
        self.input = tk.Entry(composer, bg=PANEL, fg=TEXT, insertbackground=ACCENT,
            relief='flat', font=('Segoe UI', 12))
        self.input.pack(side='left', fill='x', expand=True, ipady=8)
        self.input.bind('<Return>', lambda event: self.submit())
        self.button(composer, 'Send  ↗', self.submit, True).pack(side='right', padx=(8, 0))
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill='x', padx=24, pady=(9, 18))
        self.speak_results = tk.BooleanVar(value=True)
        tk.Checkbutton(footer, text='Speak replies', variable=self.speak_results, bg=BG, fg=MUTED,
            selectcolor=PANEL, activebackground=BG, font=('Segoe UI', 9)).pack(side='left')
        tk.Label(footer, text='Enter to send • Stop prevents the next action', bg=BG, fg=MUTED,
            font=('Segoe UI', 8)).pack(side='right')

    def append(self, who, message):
        if message:
            self.chat.configure(state='normal')
            self.chat.insert('end', who.upper() + '\n', 'name')
            self.chat.insert('end', str(message) + '\n\n')
            self.chat.configure(state='disabled')
            self.chat.see('end')

    def submit(self):
        if self.stopping:
            return
        message = self.input.get().strip()
        if not message:
            return
        if not self.connected:
            self.detail.set('Assistant is not connected yet. Your typed command has been kept.')
            return
        self.input.delete(0, 'end')
        self.append('You', message)
        self.last_transcript = message
        self.requests.put(('submit', '/api/tasks', {'message': message, 'source': 'laptop', 'speak': self.speak_results.get(), 'request_id':uuid.uuid4().hex}))

    def stop(self):
        self.requests.put(('cancel', '/api/tasks/active/cancel', {}))
        self.detail.set('Stopping after the current action. Completed actions are not undone.')

    def toggle_mic(self):
        self.requests.put(('config', '/api/config', {'microphone_paused': not self.mic_paused}))

    def stop_assistant(self):
        if self.stopping:
            return
        self.stopping = True
        self.launch_core = False
        self.detail.set('Stopping microphone, speech and tasks…')
        self.ambient.update({'status':'sleeping','active_session':False})
        def shutdown():
            try:
                request('/api/shutdown', {}, timeout=5)
                self.events.put(('shutdown', {}))
            except Exception:
                self.events.put(('stop_failed', {}))
        # Do not put emergency stop behind queued commands or enrollment requests.
        threading.Thread(target=shutdown, daemon=True, name='JoJo stop').start()

    def uninstall(self):
        from jojo_uninstall import removal_plan, launch
        try:
            plan = removal_plan()
        except Exception as exc:
            messagebox.showerror('Cannot uninstall', str(exc), parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title('Uninstall JoJo from this laptop')
        win.transient(self.root); win.grab_set()
        text = ('Permanently delete this entire folder, including source code, local memory, voice profile, saved keys, logs and APK builds:\n\n'
            + plan['root'] + '\nPrivate data: '+plan['data_dir']+'\n\nRemove the Windows startup entry and stop JoJo. This cannot be undone.\n'
            'Android must be uninstalled on the phone separately. Shared Python/SDKs, other downloads, backups and OS history are not removed.')
        tk.Label(win, text=text, wraplength=480, justify='left', padx=20, pady=15).pack()
        cloud = tk.BooleanVar(value=False)
        tk.Checkbutton(win, text='Also permanently erase shared JoJo Firestore memory', variable=cloud).pack(padx=15)
        tk.Label(win, text='Affects phone and laptop: current jojo_memory namespace plus\nuser_profile, learned_skills, conversations, notes, reminders,\njojo_remote_commands. Other namespaces/project services remain.\nIf cloud cleanup fails, local files are kept for retry.', justify='left').pack(padx=20, pady=8)
        tk.Label(win, text='Type DELETE to confirm:').pack()
        confirmation = tk.Entry(win); confirmation.pack(pady=8)
        def confirmed():
            if confirmation.get() != 'DELETE':
                return
            try:
                report = launch(plan, cloud.get())
            except Exception as exc:
                messagebox.showerror('Uninstall could not start', str(exc), parent=win)
                return
            win.destroy()
            self.launch_core=False
            self.append('Uninstall', 'Removal helper started. Final result: ' + str(report))
            self.stop_assistant()
        self.button(win, 'Permanently uninstall', confirmed).pack(pady=8)
        self.button(win, 'Cancel', win.destroy).pack(pady=(0,15))

    def settings(self):
        win = tk.Toplevel(self.root)
        win.title('JoJo Settings')
        win.configure(bg=BG)
        win.transient(self.root)
        win.geometry(f'460x540+{max(0, self.root.winfo_x()+30)}+{max(0, self.root.winfo_y()+50)}')
        from jojo_install import gui as account_setup
        self.button(win,'My model & Firebase setup',lambda:account_setup(self.root)).pack(pady=5)
        tk.Label(win, text='VOICE & WINDOW', bg=BG, fg=ACCENT, font=('Segoe UI', 13, 'bold')).pack(pady=(20, 16))
        tk.Label(win, text='Microphone', bg=BG, fg=TEXT).pack()
        mic = ttk.Combobox(win, state='readonly', values=list(self.microphones), width=48)
        mic.set(next((name for name, id in self.microphones.items() if id == self.audio_device_id), 'Windows default'))
        mic.pack(pady=7)
        language = ttk.Combobox(win, state='readonly', values=['Hindi / Hinglish', 'English (India)'])
        language.current(0 if self.speech_language == 'hi-IN' else 1)
        language.pack(pady=8)
        barge=tk.BooleanVar(value=self.barge_in_enabled)
        tk.Checkbutton(win,text='Headphone interruption (say JoJo while speaking)',variable=barge,bg=BG,fg=TEXT,selectcolor=PANEL).pack(pady=4)
        topmost = tk.BooleanVar(value=bool(self.root.attributes('-topmost')))
        tk.Checkbutton(win, text='Keep window on top', variable=topmost, bg=BG, fg=TEXT,
            selectcolor=PANEL, command=lambda: self.root.attributes('-topmost', topmost.get())).pack(pady=4)
        def save():
            self.requests.put(('config', '/api/config', {'audio_device_id': self.microphones.get(mic.get(), -1),
                'speech_language': 'hi-IN' if language.current() == 0 else 'en-IN', 'barge_in_enabled':barge.get()}))
            win.destroy()
        self.button(win, 'Save settings', save, True).pack(pady=12)
        def enroll():
            self.append('Voice enrollment', 'Ab 9 seconds tak normal awaaz mein bolte rahiye: JoJo, main aapka boss hoon, meri awaaz yaad rakho.')
            self.requests.put(('enroll', '/api/enroll_boss', {}))
        self.button(win, 'Enroll owner voice (9 seconds)', enroll).pack()
        def pair():
            def fetch():
                try:
                    self.events.put(('pair', request('/api/mobile_pairing')))
                except Exception as exc:
                    self.events.put(('error', 'Pairing unavailable: ' + type(exc).__name__))
            threading.Thread(target=fetch, daemon=True).start()
        self.button(win, 'Pair native Android companion', pair).pack(pady=8)
        self.button(win, 'Quit assistant & microphone', self.stop_assistant).pack(pady=8)
        tk.Label(win, text='Local neural voice match • Re-enroll after this upgrade.', bg=BG, fg=MUTED,
            font=('Segoe UI', 9)).pack(pady=8)

    def animate(self):
        if self.closed.is_set():
            return
        self.phase += .07
        self.canvas.delete('orb')
        busy = self.activity in ('thinking', 'speaking', 'running')
        color = ACCENT if busy else '#5c91b2'
        radius = 42 + math.sin(self.phase) * (5 if busy else 2)
        for i in range(3):
            r = radius + i*8
            self.canvas.create_oval(140-r, 66-r*.76, 140+r, 66+r*.76, outline=color if i == 0 else '#203e51', width=2, tags='orb')
        for i in range(38):
            a = i*math.pi*2/38 + self.phase*.3
            x, y = 140+math.cos(a)*radius, 66+math.sin(a)*radius*.76
            self.canvas.create_oval(x-1.5, y-1.5, x+1.5, y+1.5, fill=color, outline='', tags='orb')
        for i in range(13):
            h = 4 + abs(math.sin(self.phase+i*.65))*(21 if busy else 10)
            self.canvas.create_line(104+i*6, 66-h, 104+i*6, 66+h, fill=color, width=3, tags='orb')
        self.root.after(50, self.animate)

    def owner_setup(self):
        import secrets
        from jojo_user_config import owner, private_dir
        win=tk.Toplevel(self.root);win.title('JoJo • Meet your owner');win.transient(self.root)
        tk.Label(win,text='Let JoJo learn your voice',font=('Segoe UI',18,'bold')).pack(padx=24,pady=18)
        tk.Label(win,text='Owner name').pack();name=tk.Entry(win,width=48);name.insert(0,owner()['name']);name.pack(pady=5)
        tk.Label(win,text='Optional details (stored locally; may enter your AI context)').pack();details=tk.Entry(win,width=48);details.insert(0,owner().get('details',''));details.pack(pady=5)
        challenge=' '.join(str(secrets.randbelow(10)) for _ in range(6))
        tk.Label(win,text=challenge,font=('Segoe UI',25,'bold')).pack(pady=14)
        tk.Label(win,text='Read these numbers, then speak continuously for 9 seconds:\n“JoJo, I am your owner. Listen to my voice and help me with my tasks.”\n\nThe voice embedding stays local. This is not replay-proof authentication.\nThe text is a reading prompt, not a verified liveness challenge.',wraplength=490).pack(padx=20,pady=8)
        def enroll():
            if not name.get().strip():return
            directory=private_dir();directory.mkdir(parents=True,exist_ok=True)
            account=directory/'jojo_account.json'
            if account.exists():
                value=json.loads(account.read_text(encoding='utf-8'));value.update(owner_name=name.get().strip()[:120],owner_details=details.get()[:2000])
                temp=account.with_suffix('.tmp');temp.write_text(json.dumps(value),encoding='utf-8');temp.replace(account)
            else:
                (directory/'jojo_owner_identity.json').write_text(json.dumps({'name':name.get().strip()[:120],'details':details.get()[:2000]}),encoding='utf-8')
            self.append('Voice enrollment','Read the numbers '+challenge+' and the phrase for 9 seconds. Wait for the success/failure result here.')
            record_button.configure(state='disabled',text='Recording… keep reading the numbers and phrase')
            self.enrollment_window=win;self.enrollment_button=record_button
            self.requests.put(('enroll','/api/enroll_boss',{}))
        record_button=self.button(win,'Start 9-second recording',enroll);record_button.pack(pady=18)

    def skills(self):
        def fetch():
            try:self.events.put(('skills',request('/api/skills')))
            except Exception as exc:self.events.put(('error','Skill settings unavailable: '+type(exc).__name__))
        threading.Thread(target=fetch,daemon=True).start()

    def network_loop(self):
        pending, process, started, devices_loaded = set(), None, False, False
        while not self.closed.is_set():
            if self.stopping:
                self.closed.wait(.1)
                continue
            try:
                health = request('/api/health')
                if health.get('service') != 'jojo' or health.get('version', 0) < 2:
                    raise ValueError('An older or different service is using port 8000. Restart JoJo.')
                self.events.put(('connected', health))
                if not devices_loaded:
                    self.events.put(('history', request('/api/memory/history')))
                    self.events.put(('devices', request('/api/audio_devices')))
                    devices_loaded = True
                try:
                    kind, path, data = self.requests.get_nowait()
                except queue.Empty:
                    pass
                else:
                    if self.stopping:
                        continue
                    try:
                        result = request(path, data, timeout=30 if kind == 'enroll' else 2)
                        if kind == 'submit' and result.get('id'):
                            pending.add(result['id'])
                        self.events.put((kind, result))
                    except Exception as exc:
                        self.events.put(('enroll_failed' if kind=='enroll' else 'error', 'Request could not be confirmed (' + type(exc).__name__ + '). Check progress before retrying.'))
                state = request('/api/voice_state')
                if state.get('task'):
                    pending.add(state['task']['id'])
                self.events.put(('state', state))
                for task_id in tuple(pending):
                    try:
                        task = request('/api/tasks/' + task_id)
                    except urllib.error.HTTPError as exc:
                        if exc.code != 404:
                            raise
                        pending.discard(task_id)
                        self.events.put(('error', 'The core restarted or a task expired. Its completion is unknown; it was not resubmitted.'))
                        continue
                    self.events.put(('task', task))
                    if task['status'] in TERMINAL:
                        pending.discard(task_id)
            except urllib.error.HTTPError as exc:
                self.events.put(('offline', 'Restart JoJo to load the updated backend.' if exc.code == 404 else 'Assistant API error: ' + str(exc.code)))
            except (OSError, ValueError) as exc:
                if self.launch_core and not started and not isinstance(exc, ValueError):
                    started = True
                    try:
                        process = start_core()
                    except OSError as error:
                        self.events.put(('error', 'Could not start JoJo: ' + str(error)))
                message = str(exc) if isinstance(exc, ValueError) else 'Connecting to JoJo…'
                if process is not None and process.poll() is not None:
                    message = 'Core stopped. See logs/core.log for the startup error.'
                self.events.put(('offline', message))
            self.closed.wait(.65)

    def drain_events(self):
        if self.closed.is_set():
            return
        for _ in range(40):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'connected':
                self.connected = True
                self.connection.set('●  CONNECTED')
            elif kind == 'offline':
                self.connected = False
                self.connection.set('●  OFFLINE')
                self.status.set('Assistant is reconnecting')
                self.detail.set(data)
            elif kind == 'devices':
                for device in data.get('devices', []) if isinstance(data, dict) else data:
                    self.microphones[f"{device['id']}: {device['name']}"] = device['id']
            elif kind == 'history':
                for turn in data:
                    self.append('You · saved', turn['message'])
                    if turn.get('reply'):
                        self.append('JoJo · ' + turn['status'], turn['reply'])
                    if turn['status'] in TERMINAL:
                        self.seen.add(turn['id'])
            elif kind == 'state':
                self.ambient.update(data)
                security=data.get('security') or {}
                alert=security.get('alert_id','')
                if alert and alert != self.last_security_alert:
                    self.last_security_alert=alert
                    self.security_warning(security)
                if not alert:
                    self.last_security_alert=''
                scan=security.get('defender_scan') or {}
                if scan.get('status','idle') != self.last_security_scan:
                    self.last_security_scan=scan.get('status','idle')
                    self.append('Defender scan',scan.get('message',''))
                if self.initial_state:
                    self.initial_state = False
                    if data.get('owner_enrolled'):
                        self.root.withdraw()
                    else:
                        self.root.deiconify()
                        if not self.setup_shown:
                            self.setup_shown=True;self.root.after(400,self.owner_setup)
                self.audio_device_id = data.get('audio_device_id') if data.get('audio_device_id') is not None else -1
                self.speech_language = data.get('speech_language', 'hi-IN')
                self.barge_in_enabled=data.get('barge_in_enabled',False)
                self.activity = data.get('status', 'idle')
                self.mic_paused = data.get('microphone_paused', False)
                self.mic_button.configure(text='Resume mic' if self.mic_paused else 'Pause mic')
                active = data.get('task')
                labels = {'sleeping': 'Say “JoJo” to begin', 'listening': 'Listening…', 'speaking': 'Speaking…',
                    'thinking': 'Working on your request', 'access_denied': 'Voice match unclear'}
                self.status.set('Microphone paused' if self.mic_paused else labels.get(self.activity, 'Ready'))
                self.detail.set(data.get('audio_error') or (active or {}).get('progress') or 'Ready for your next request')
                transcript = data.get('transcript', '')
                if transcript and transcript != self.last_transcript:
                    self.append('You · heard', transcript)
                    self.last_transcript = transcript
                reply = data.get('reply', '')
                if not active and reply and reply != self.last_reply:
                    self.append('JoJo', reply)
                    self.last_reply = reply
            elif kind == 'task':
                if data['status'] not in TERMINAL:
                    self.activity = 'running'
                    self.detail.set(data['progress'])
                elif data['id'] not in self.seen:
                    self.seen.add(data['id'])
                    if data['reply'] != self.last_reply:
                        self.append('JoJo · ' + data['status'].replace('_', ' '), data['reply'] or data['error'])
                        self.last_reply = data['reply']
                    self.status.set(data['status'].replace('_', ' ').capitalize())
            elif kind == 'error':
                self.append('Connection', data)
            elif kind == 'cancel':
                self.detail.set(data.get('progress', data.get('reply', 'Stop requested.')))
            elif kind == 'enroll':
                self.append('Voice enrollment', data.get('message', str(data)))
                window=getattr(self,'enrollment_window',None)
                if window is not None and window.winfo_exists():window.destroy()
            elif kind == 'enroll_failed':
                self.append('Voice enrollment',data)
                button=getattr(self,'enrollment_button',None)
                if button is not None and button.winfo_exists():button.configure(state='normal',text='Retry 9-second recording')
            elif kind == 'skills':
                win=tk.Toplevel(self.root);win.title('JoJo • Skills & plugins');win.geometry('620x700');switches={}
                tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=12,pady=12)
                for label,items in [('Categories',data['skills']),('Individual tools',data.get('tools',[]))]:
                    page=tk.Frame(tabs);tabs.add(page,text=label)
                    canvas=tk.Canvas(page,highlightthickness=0);bar=ttk.Scrollbar(page,orient='vertical',command=canvas.yview)
                    canvas.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
                    content=tk.Frame(canvas);canvas.create_window((0,0),window=content,anchor='nw')
                    content.bind('<Configure>',lambda event,c=canvas:c.configure(scrollregion=c.bbox('all')))
                    for skill in items:
                        value=tk.BooleanVar(value=skill['enabled']);switches[skill['id']]=value
                        tk.Checkbutton(content,text=skill['name'],variable=value).pack(anchor='w',padx=10)
                        tk.Label(content,text=skill['description'],wraplength=500,justify='left').pack(anchor='w',padx=30,pady=(0,8))
                plugins=tk.Frame(tabs);tabs.add(plugins,text='Plugins')
                for plugin in data.get('plugins',[]):tk.Label(plugins,text=plugin['name']+'\nLocked off: '+plugin['reason'],wraplength=520,justify='left').pack(padx=15,pady=20)
                tk.Label(win,text='Executable plugins remain disabled. Memory switch controls memory tools;\nconversation history is still recorded. Clear history separately.').pack(padx=20,pady=10)
                self.button(win,'Save switches',lambda:(self.requests.put(('skills_saved','/api/skills',{key:value.get() for key,value in switches.items()})),win.destroy())).pack(pady=12)
            elif kind == 'skills_saved':
                self.append('Skills','Your skill switches are saved. Disabled tools are blocked on the next action.')
            elif kind == 'security_scan':
                self.append('Defender scan',data.get('message','Scan status unavailable.'))
            elif kind == 'pair':
                win = tk.Toplevel(self.root)
                win.title('JoJo Android pairing')
                tk.Label(win, text='Enter this key in the native Android app.\nUse USB debugging and adb reverse tcp:8000 tcp:8000.', padx=20, pady=15).pack()
                entry = tk.Entry(win, width=62)
                entry.insert(0, data['key'])
                entry.configure(state='readonly')
                entry.pack(padx=20, pady=15)
            elif kind == 'shutdown':
                self.closed.set()
                self.root.destroy()
                return
            elif kind == 'stop_failed':
                self.stopping=False
                self.detail.set('Stop could not be confirmed. Retry Stop JoJo; no automatic restart will be attempted.')
        self.root.after(80, self.drain_events)

    def close(self):
        # Keep the event loop alive so wake-word overlays continue to work.
        self.root.withdraw()

    def security_warning(self, report):
        from jojo_security import format_report
        self.append('Security warning', format_report(report))
        popup=tk.Toplevel(self.root)
        popup.title('JoJo security warning')
        popup.configure(bg=PANEL)
        popup.attributes('-topmost',True)
        popup.geometry(f'440x230+{max(0,self.root.winfo_screenwidth()-470)}+55')
        tk.Label(popup,text='Protection needs attention',bg=PANEL,fg='#ffca80',font=('Segoe UI',14,'bold')).pack(pady=18)
        important=[f['message'] for f in report.get('findings',[]) if f['level'] in ('high','critical')]
        tk.Label(popup,text='\n'.join(important[:2])+'\nThis does not by itself prove the device is hacked.',wraplength=395,bg=PANEL,fg=TEXT).pack(padx=15)
        self.button(popup,'View report',lambda:(self.root.deiconify(),popup.destroy())).pack(pady=14)

def main():
    if os.name == 'nt':
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    preview = '--preview' in sys.argv
    if not preview and not claim_instance('desktop'):
        if '--background' in sys.argv:
            return
        from jojo_overlay import show_jojo_hud
        show_jojo_hud()
        return
    root = tk.Tk()
    if '--background' in sys.argv:
        root.withdraw()
    desktop = JoJoDesktop(root, launch_core=True, preview=preview)
    if '--overlay-preview' in sys.argv:
        root.withdraw()
        def demo(index=0):
            states = ['listening', 'thinking', 'working', 'speaking']
            desktop.ambient.update({'status': states[index % 4], 'active_session': True})
            root.after(3000, lambda: demo(index+1))
        demo()
        root.after(60000, root.destroy)
    root.mainloop()

if __name__ == '__main__':
    main()
