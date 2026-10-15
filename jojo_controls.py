"""Local stop signal, Windows global hotkeys and scoped emergency shutdown."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import threading
import time

def signal_stop():
    from jojo_config import DATA_DIR
    path=DATA_DIR/'jojo_stop.signal'
    path.write_text(str(time.time_ns()),encoding='ascii')

def disable_startup(root=None, startup=None):
    root=Path(root or Path(__file__).resolve().parent)
    startup=Path(startup or Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup')
    (startup/'jojo_autostart.vbs').unlink(missing_ok=True)
    (root/'.no_autostart').touch()

def terminate_backend(root=None):
    """Kill only this installation's core process tree; no optional dependency."""
    import subprocess
    root=Path(root or Path(__file__).resolve().parent).resolve()
    # Match a whole command-line argument; avoid other installations and other Python apps.
    pattern = r'(?i)(?:^|[\s"])' + __import__('re').escape(str(root/'jojo_core.py')) + r'(?=[\s"]|$)'
    script = "$pattern = '" + pattern.replace("'", "''") + "'; "
    script += ("Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | "
        "Where-Object { $_.CommandLine -match $pattern } | ForEach-Object { "
        "& taskkill.exe /PID $_.ProcessId /T /F | Out-Null }")
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
        capture_output=True,timeout=8,check=True,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


class GlobalHotkeys:
    def __init__(self, callback):
        self.callback=callback
        self.thread_id=None
    def start(self):
        if os.name=='nt':
            threading.Thread(target=self.run,daemon=True,name='JoJo hotkeys').start()
    def run(self):
        user=ctypes.windll.user32
        thread_id=ctypes.windll.kernel32.GetCurrentThreadId()
        # Create the thread message queue before making its ID available.
        msg=wintypes.MSG()
        user.PeekMessageW(ctypes.byref(msg),None,0,0,0)
        self.thread_id=thread_id
        registered=[]
        try:
            for identifier,key in ((1,0x4A),(2,0x51)):
                if user.RegisterHotKey(None,identifier,0x0002|0x0004|0x4000,key):
                    registered.append(identifier)
                else:
                    self.callback('error','Shortcut unavailable: Ctrl+Shift+'+chr(key)+'. Another app may own it.')
            while user.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                if msg.message==0x0312:
                    self.callback('hotkey',int(msg.wParam))
        finally:
            for identifier in registered:user.UnregisterHotKey(None,identifier)
    def close(self):
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id,0x0012,0,0)
