"""Compatibility launcher for the native desktop window."""
import ctypes
from pathlib import Path
import subprocess
import sys

def find_jojo_hud_window():
    if sys.platform != "win32":
        return None
    user = ctypes.windll.user32
    user.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user.FindWindowW.restype = ctypes.c_void_p
    return user.FindWindowW(None, "JoJo Desktop")

def minimize_jojo_hud():
    hwnd = find_jojo_hud_window()
    if hwnd:
        ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), 6)
    return bool(hwnd)

def show_jojo_hud():
    hwnd = find_jojo_hud_window()
    if hwnd:
        ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), 9)
        ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    return bool(hwnd)

def launch_native_desktop_hud(hud_url=None):
    if show_jojo_hud():
        return True
    script = Path(__file__).with_name("jojo_desktop.py")
    subprocess.Popen([sys.executable, str(script), "--start-core"], cwd=str(script.parent),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True

if __name__ == "__main__":
    from jojo_desktop import main
    main()
