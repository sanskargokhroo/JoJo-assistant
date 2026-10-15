"""Run once to enable current-user Windows login startup and launch native JoJo."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def install_launch_shortcut(root=ROOT, python=None, programs=None):
    """Explorer owns this shortcut, so no JoJo listener must stay running."""
    root=Path(root).resolve()
    python=Path(python or sys.executable).with_name('pythonw.exe')
    if not python.is_file():raise RuntimeError('pythonw.exe not found.')
    programs=Path(programs or Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs')
    target=programs/'JoJo/JoJo.lnk'
    env=dict(os.environ, JOJO_LINK_PATH=str(target), JOJO_LINK_PYTHON=str(python),
             JOJO_LINK_ROOT=str(root), JOJO_LINK_ARGS=subprocess.list2cmdline([str(root/'jojo_start.py'),'--no-autostart']))
    script="""$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $env:JOJO_LINK_PATH) | Out-Null
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut($env:JOJO_LINK_PATH)
$link.TargetPath=$env:JOJO_LINK_PYTHON
$link.Arguments=$env:JOJO_LINK_ARGS
$link.WorkingDirectory=$env:JOJO_LINK_ROOT
$link.Description='Start JoJo (Ctrl+Alt+J)'
$link.Hotkey='CTRL+ALT+J'
$link.Save()
"""
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                   env=env,check=True,capture_output=True,timeout=15,
                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return target


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
    if not args.disable_autostart:
        try:install_launch_shortcut()
        except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
            print('Launch shortcut could not be installed:',type(exc).__name__)
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
