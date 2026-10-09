"""Restore JoJo's USB tunnel on already-authorized Android devices after reconnect."""
import os
from pathlib import Path
import shutil
import subprocess
import threading

def find_adb():
    candidates = [Path(os.environ.get('ANDROID_HOME', '')) / 'platform-tools/adb.exe',
                  Path.home() / 'AppData/Local/Android/Sdk/platform-tools/adb.exe']
    return next((str(path) for path in candidates if path.is_file()), shutil.which('adb'))

def restore(adb):
    def run(*args):
        return subprocess.run([adb, *args], capture_output=True, text=True, timeout=8,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    devices = run('devices')
    if devices.returncode:
        return
    for line in devices.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) != 2 or fields[1] != 'device':
            continue
        serial = fields[0]
        # Do not change forwarding on unrelated attached devices.
        installed = run('-s', serial, 'shell', 'pm', 'path', 'app.jojo.nativevoice')
        if installed.returncode or not installed.stdout.strip().startswith('package:'):
            continue
        current = run('-s', serial, 'reverse', '--list')
        if not any(row.split()[-2:] == ['tcp:8000', 'tcp:8000'] for row in current.stdout.splitlines()):
            run('-s', serial, 'reverse', 'tcp:8000', 'tcp:8000')

def start(stop):
    if os.environ.get('JOJO_DISABLE_USB_RECONNECT') == '1' or os.environ.get('JOJO_PORT', '8000') != '8000':
        return
    adb = find_adb()
    if not adb:
        return
    def worker():
        while not stop.is_set():
            try:
                restore(adb)
            except (OSError, subprocess.TimeoutExpired):
                pass
            stop.wait(15)
    threading.Thread(target=worker, name='JoJo USB reconnect', daemon=True).start()
