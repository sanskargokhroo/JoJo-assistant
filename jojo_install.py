"""JoJo setup: python jojo_install.py --cli, or --gui (default). No bundled accounts."""
import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys
import threading
import venv
from jojo_user_config import save, private_dir

ROOT=Path(__file__).resolve().parent

def install_dependencies(status=print):
    if os.name!='nt':raise RuntimeError('The native desktop release currently supports Windows only.')
    directory=ROOT/'.venv'
    python=directory/'Scripts/python.exe'
    if not python.exists():
        status('Creating an isolated Python environment…');venv.EnvBuilder(with_pip=True).create(directory)
    private_dir().mkdir(parents=True,exist_ok=True)
    with (private_dir()/'jojo_install.log').open('a',encoding='utf-8') as log:
        status('Installing requirements. This may take several minutes…')
        subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements.txt')],stdout=log,stderr=log,check=True,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        status('Installing and verifying the local voice model…')
        subprocess.run([str(python),str(ROOT/'jojo_setup_voice.py')],stdout=log,stderr=log,check=True,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    status('Installation complete. Configure your own accounts, then enroll your voice.')
    return python

def launch_desktop():
    python=ROOT/'.venv/Scripts/pythonw.exe'
    if not python.exists():raise RuntimeError('Install dependencies first.')
    subprocess.Popen([str(python),str(ROOT/'jojo_start.py')],cwd=ROOT)

def cli():
    print('JoJo • your device, your accounts\nWindows desktop + Android companion. Internet/API usage may incur provider charges.')
    if input('Install dependencies and voice model now? [y/N] ').lower()=='y':install_dependencies()
    provider=input('Provider [gemini/openai/anthropic]: ').strip().lower()
    model=input('Exact model ID (must support tools and vision for full features): ').strip()
    key=getpass.getpass('Your provider API key (hidden): ')
    print('Firebase is optional. Use your own service-account JSON; a Firebase browser API key alone is insufficient.')
    firebase=input('Firebase service-account JSON path, or Enter for local-only memory: ').strip().strip('"')
    name=input('What should JoJo call its owner? ').strip()
    details=input('Optional profile details (local, included in your AI context): ').strip()
    path=save(provider,model,key,firebase,name,details)
    print('Saved privately:',path,'\nAPI/Firebase secrets use Windows current-user encryption. Never share this directory.')
    print('Next: open JoJo → Owner setup → read the displayed challenge to enroll. Voice is not replay-proof.')
    if input('Open the dashboard now? [y/N] ').lower()=='y':launch_desktop()

def gui(parent=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    win=tk.Toplevel(parent) if parent else tk.Tk();win.title('JoJo • First-time setup');win.geometry('640x730')
    win.configure(bg='#0b1020')
    frame=tk.Frame(win,bg='#0b1020',padx=28,pady=20);frame.pack(fill='both',expand=True)
    tk.Label(frame,text='JOJO / MAKE IT YOURS',font=('Segoe UI',22,'bold'),bg='#0b1020',fg='#6ce5e8').pack(anchor='w')
    tk.Label(frame,text='Your model. Your Firebase project. Your private owner profile.\nNo developer accounts are included.',bg='#0b1020',fg='white',justify='left').pack(anchor='w',pady=12)
    fields={}
    def field(label,name,secret=False):
        tk.Label(frame,text=label,bg='#0b1020',fg='white').pack(anchor='w',pady=(8,2))
        widget=tk.Entry(frame,show='•' if secret else '');widget.pack(fill='x');fields[name]=widget
    tk.Label(frame,text='Model provider',bg='#0b1020',fg='white').pack(anchor='w')
    provider=ttk.Combobox(frame,values=['gemini','openai','anthropic'],state='readonly');provider.set('gemini');provider.pack(fill='x')
    field('Exact model ID (tool + vision capable)','model')
    field('Your model API key — hidden; not a ChatGPT subscription login','key',True)
    field('Optional Firebase service-account JSON path','firebase')
    tk.Button(frame,text='Choose your Firebase JSON',command=lambda:(fields['firebase'].delete(0,'end'),fields['firebase'].insert(0,filedialog.askopenfilename(parent=win,filetypes=[('JSON','*.json')])))).pack(anchor='w')
    field('Owner display name','name');field('Optional owner details','details')
    status=tk.StringVar(value='Use local-only memory by leaving Firebase empty. Voice enrollment happens next.')
    tk.Label(frame,textvariable=status,wraplength=575,justify='left',bg='#0b1020',fg='#a6b8cd').pack(pady=14)
    def install():
        install_button.configure(state='disabled')
        def work():
            try:install_dependencies(lambda text:win.after(0,status.set,text))
            except Exception as exc:win.after(0,status.set,'Install failed: '+type(exc).__name__+'. See private jojo_install.log.')
            finally:win.after(0,lambda:install_button.configure(state='normal'))
        threading.Thread(target=work,daemon=True).start()
    install_button=tk.Button(frame,text='1 · Install dependencies + voice model',command=install);install_button.pack(fill='x',pady=5)
    def persist():
        try:
            save(provider.get(),fields['model'].get(),fields['key'].get(),fields['firebase'].get(),fields['name'].get(),fields['details'].get())
            fields['key'].delete(0,'end')
            status.set('Saved privately. Restart JoJo if already running, then complete Owner setup. Never upload your private data folder.')
        except Exception as exc:messagebox.showerror('Setup',str(exc),parent=win)
    tk.Button(frame,text='2 · Save my private setup',command=persist).pack(fill='x',pady=5)
    def open_app():
        try:launch_desktop()
        except Exception as exc:messagebox.showerror('Setup',str(exc),parent=win)
    tk.Button(frame,text='3 · Open JoJo and enroll my voice',command=open_app).pack(fill='x',pady=5)
    if not parent:win.mainloop()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cli',action='store_true');parser.add_argument('--gui',action='store_true')
    args=parser.parse_args();cli() if args.cli else gui()
