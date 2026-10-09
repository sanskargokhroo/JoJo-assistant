"""Render the native workspace with synthetic data only; no live assistant API."""
import sys
from pathlib import Path
import tkinter as tk
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jojo_workspace_ui import open_workspace

def fixture(path,data=None,timeout=1):
    return {'private_session':False,'cards':[{'id':'fixture','text':'Use concise Hinglish replies','kind':'preference'}],
            'documents':[],'routines':[],'history':[],'permissions':[],'undo':[],'schedules':[],'handoffs':[],
            'metrics':{'recorded_terminal_tasks':0,'note':'Synthetic preview data'}}

def main():
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
    root=tk.Tk();root.withdraw()
    try:
        open_workspace(root,fixture)
        for _ in range(12):root.update();time.sleep(.1)
        window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
        from PIL import ImageGrab
        path=Path(__file__).resolve().parents[1]/'.jojo-private/jojo_workspace_preview.png'
        path.parent.mkdir(exist_ok=True)
        ImageGrab.grab(bbox=(window.winfo_rootx(),window.winfo_rooty(),window.winfo_rootx()+window.winfo_width(),window.winfo_rooty()+window.winfo_height())).save(path)
        print('Native workspace rendered:',path)
    finally:root.destroy()

if __name__=='__main__':main()
