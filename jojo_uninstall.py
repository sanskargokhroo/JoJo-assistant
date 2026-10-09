"""Prepare a local, explicit uninstall; never exposed as an AI tool or HTTP API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent

def validate_root(root):
    root = Path(root).absolute()
    if root.is_symlink() or root.is_junction() or root.resolve() != root:
        raise ValueError('Uninstall refuses linked install directories.')
    if root == Path(root.anchor) or root == Path.home() or len(root.parts) < 2:
        raise ValueError('Unsafe install directory.')
    for marker in ('jojo_core.py', 'jojo_desktop.py', 'jojo_start.py', 'jojo_uninstall.ps1'):
        if not (root / marker).is_file():
            raise ValueError('Not a recognized JoJo installation.')
    return root

def removal_plan():
    from jojo_config import DATA_DIR
    root = validate_root(ROOT)
    data = DATA_DIR.resolve()
    if data != root and root not in data.parents:
        standard=(Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'JoJo').resolve()
        if data != standard:
            raise ValueError('JOJO_DATA_DIR is outside the install folder and standard JoJo user folder. Custom data is not deleted automatically.')
    return {'root': str(root), 'data_dir':str(data), 'startup': str(Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Startup/jojo_autostart.vbs')}

def launch(plan, erase_cloud):
    # Revalidate at action time, not only when the confirmation window opened.
    if plan != removal_plan():
        raise ValueError('Install paths changed; reopen uninstall.')
    helper = Path(tempfile.mkdtemp(prefix='JoJo-uninstall-'))
    script = helper / 'remove.ps1'
    shutil.copyfile(ROOT / 'jojo_uninstall.ps1', script)
    manifest = dict(plan, python=str(Path(sys.executable).with_name('python.exe')), erase_cloud=bool(erase_cloud))
    (helper / 'plan.json').write_text(json.dumps(manifest), encoding='utf-8')
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    subprocess.Popen([str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
        cwd=helper, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return helper / 'result.txt'
