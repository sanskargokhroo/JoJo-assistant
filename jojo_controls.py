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
    """Kill only this installation's core tree, resolving Windows short paths."""
    import json
    import subprocess
    root=Path(root or Path(__file__).resolve().parent).resolve()
    script = ("Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | "
              "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
        capture_output=True,text=True,timeout=8,check=True,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    records=json.loads(result.stdout or '[]')
    if isinstance(records,dict):records=[records]
    shell=ctypes.windll.shell32
    shell.CommandLineToArgvW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype=ctypes.POINTER(wintypes.LPWSTR)
    kernel=ctypes.windll.kernel32
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    for record in records or []:
        command=record.get('CommandLine')
        if not command:continue
        count=ctypes.c_int()
        argv=shell.CommandLineToArgvW(command,ctypes.byref(count))
        if not argv:continue
        try:arguments=[argv[i] for i in range(count.value)]
        finally:kernel.LocalFree(argv)
        expected=root/'jojo_core.py'
        matches=False
        for argument in arguments[1:]:
            try:
                path=Path(argument)
                if path.is_absolute() and path.resolve()==expected:
                    matches=True
            except (ValueError,OSError):pass
        if matches:
            subprocess.run(['taskkill.exe','/PID',str(int(record['ProcessId'])),'/T','/F'],
                capture_output=True,timeout=5,check=True,
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
