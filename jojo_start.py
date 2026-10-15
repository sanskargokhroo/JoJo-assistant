"""Run once to enable current-user Windows login startup and launch native JoJo."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def launcher_text(root, python):
    def vb(value):
        return '"' + str(value).replace('"', '""') + '"'
    command = subprocess.list2cmdline([str(python), str(root / 'jojo_desktop.py'), '--start-core', '--background'])
    return ('Set shell = CreateObject("WScript.Shell")\r\n'
            + 'shell.CurrentDirectory = ' + vb(root) + '\r\n'
            + 'shell.Run ' + vb(command) + ', 0, False\r\n')

def install(startup, root=ROOT, python=None):
    python = Path(python or sys.executable).with_name('pythonw.exe')
    if not python.is_file():
        raise RuntimeError('pythonw.exe not found beside this Python installation.')
    target = startup / 'jojo_autostart.vbs'
    startup.mkdir(parents=True, exist_ok=True)
    target.write_text(launcher_text(root, python), encoding='utf-16')
    return target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-only', action='store_true')
    parser.add_argument('--disable-autostart', action='store_true')
    parser.add_argument('--enable-autostart', action='store_true')
    parser.add_argument('--no-autostart', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt':
        raise SystemExit('This launcher supports Windows only.')
    from jojo_user_config import load
    if not args.install_only and not args.disable_autostart and not load() and not (ROOT/'.env').exists():
        from jojo_install import gui
        gui()
        return
    startup = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Startup'
    no_autostart_marker = ROOT / '.no_autostart'
    if args.disable_autostart:
        (startup / 'jojo_autostart.vbs').unlink(missing_ok=True)
        no_autostart_marker.touch()
        print('JoJo login startup disabled. A running assistant is unchanged.')
        return
    if args.enable_autostart or args.install_only:
        no_autostart_marker.unlink(missing_ok=True)

    if not args.no_autostart and not no_autostart_marker.exists():
        target = install(startup)
        print('JoJo will start after Windows sign-in. Startup entry:', target)
    else:
        print('JoJo autostart is disabled. Running only for this session.')
    if not args.install_only:
        subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')), str(ROOT / 'jojo_desktop.py'), '--start-core'], cwd=ROOT)

if __name__ == '__main__':
    main()
