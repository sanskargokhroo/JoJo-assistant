"""Native Tk workspace; all API work happens off the UI thread."""
import json
import queue
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from tkinter.scrolledtext import ScrolledText


def open_workspace(parent, request):
    window = tk.Toplevel(parent)
    window.title('JoJo • Workspace')
    window.geometry(f'{min(1000,parent.winfo_screenwidth()-80)}x{min(690,parent.winfo_screenheight()-100)}')
    window.minsize(700, 500)
    events = queue.Queue()
    status = tk.StringVar(value='Loading local workspace…')
    private = tk.BooleanVar()
    data = {}
    widgets = {}
    busy = False

    def when(value):
        return datetime.fromtimestamp(value).strftime('%d %b, %H:%M') if value else 'Not recorded'

    def describe(key,row):
        if key=='cards':return row['text']+'\n\nType: '+row['kind']
        if key=='documents':return row['path']+'\n\nIndexed: '+when(row.get('updated'))+'\nReindex this file after editing it.'
        if key=='routines':return row['name']+'\n\n'+row['instructions']+'\n\n'+('Enabled' if row['enabled'] else 'Draft — review before enabling')
        if key=='history':return 'You: '+row['message']+'\n\nJoJo: '+row['reply']+'\n\nStatus: '+row['status']+'\n'+when(row.get('created_at'))
        if key=='permissions':return row['name']+'\n\n'+('Allowed' if row['enabled'] else 'Blocked')+'\nTemporary override remaining: '+str(row['temporary_seconds'])+' seconds.\nSaved settings resume after expiry or restart.'
        if key=='undo':return row['path']+'\n\nSaved original: '+when(row.get('created'))+'\nRestoration is refused if the file has since changed.'
        if key=='handoffs':
            context=json.loads(row['context'])
            return 'From '+row['source']+' to '+row['target']+'\n\n'+context['goal']+'\n\nLast reply: '+context['last_reply']+'\n\nExpires: '+when(row['expires'])
        if key=='schedules':return 'Every '+str(row['interval_seconds']//60)+' minutes\nNext run: '+when(row['next_run'])+'\nLast task: '+(row['last_task'] or 'Not run yet')
        return str(row)

    def call(action=None, **values):
        nonlocal busy
        if busy:
            status.set('Please wait for the current request to finish.');return
        busy = True
        status.set('Working…')
        def work():
            try:
                result = request('/api/workspace', {'action':action, **values}, timeout=40) if action else None
                snapshot = request('/api/workspace', timeout=10)
                events.put(('loaded', (snapshot, result, action)))
            except Exception as exc:
                detail = str(exc)
                if hasattr(exc, 'read'):
                    try:detail=json.loads(exc.read().decode()).get('detail',detail)
                    except Exception:pass
                events.put(('error', detail))
        threading.Thread(target=work, daemon=True, name='JoJo workspace request').start()

    header = ttk.Frame(window, padding=12);header.pack(fill='x')
    ttk.Checkbutton(header, text='Private session', variable=private,
                    command=lambda:call('privacy',enabled=private.get())).pack(side='left')
    ttk.Button(header,text='Refresh',command=call).pack(side='right')
    ttk.Label(window,text='Private session stops new conversation persistence/recall. Online models still receive requests.\nExisting history, explicit file actions and third-party app records are not erased.',wraplength=820).pack(padx=12,anchor='w')
    tabs = ttk.Notebook(window);tabs.pack(fill='both',expand=True,padx=12,pady=12)

    def panel(key, title):
        frame=ttk.Frame(tabs,padding=10);tabs.add(frame,text=title)
        panes=ttk.Panedwindow(frame,orient='horizontal');panes.pack(fill='both',expand=True,pady=(0,10))
        listing=tk.Listbox(panes,height=10,width=36,exportselection=False)
        panes.add(listing,weight=1)
        details=ScrolledText(panes,height=8,width=45,wrap='word');panes.add(details,weight=2)
        buttons=ttk.Frame(frame);buttons.pack(fill='x')
        widgets[key]=(listing,details)
        def select(event=None):
            row=selected(key)
            details.delete('1.0','end')
            if row:details.insert('end',describe(key,row))
        listing.bind('<<ListboxSelect>>',select)
        return buttons

    def selected(key):
        selection=widgets[key][0].curselection()
        return data.get(key,[])[selection[0]] if selection else None

    def need(key):
        row=selected(key)
        if not row:status.set('Select an item first.')
        return row

    def memory(edit=False):
        row=need('cards') if edit else {}
        if edit and not row:return
        text=simpledialog.askstring('JoJo memory','Preference, correction or project detail (no secrets):',
                                    initialvalue=row.get('text',''),parent=window)
        if text:call('save_memory',text=text,id=row.get('id',''),kind=row.get('kind','preference'))

    def remove(key,action):
        row=need(key)
        if row and messagebox.askyesno('JoJo','Remove this saved item? Original documents stay on disk.',parent=window):
            call(action,id=row['id'])

    b=panel('cards','Memory cards')
    ttk.Button(b,text='Add',command=memory).pack(side='left')
    ttk.Button(b,text='Edit',command=lambda:memory(True)).pack(side='left',padx=6)
    ttk.Button(b,text='Delete',command=lambda:remove('cards','delete_memory')).pack(side='left')

    def index():
        path=filedialog.askopenfilename(parent=window,filetypes=[('Knowledge files','*.txt *.md *.pdf')])
        if path:call('index_document',text=path)
    def search():
        query=simpledialog.askstring('JoJo knowledge','Search your selected documents:',parent=window)
        if query:call('search',text=query)
    b=panel('documents','Knowledge')
    ttk.Button(b,text='Add / reindex file',command=index).pack(side='left')
    ttk.Button(b,text='Search',command=search).pack(side='left',padx=6)
    ttk.Button(b,text='Remove index',command=lambda:remove('documents','delete_document')).pack(side='left')

    def routine(edit=False):
        row=need('routines') if edit else {}
        if edit and not row:return
        name=simpledialog.askstring('JoJo routine','Routine name:',initialvalue=row.get('name',''),parent=window)
        if not name:return
        instructions=simpledialog.askstring('JoJo routine','Exact steps (a draft requires review before running):',
                                            initialvalue=row.get('instructions',''),parent=window)
        if instructions:call('save_routine',name=name,text=instructions,id=row.get('id',''))
    def approve():
        row=need('routines')
        if row and messagebox.askyesno('Review routine',row['instructions']+'\n\nEnable this workflow for manual runs?',parent=window):
            call('enable_routine',id=row['id'],enabled=True)
    def run_routine():
        row=need('routines')
        if row:call('run_routine',id=row['id'])
    def disable():
        row=need('routines')
        if row:call('enable_routine',id=row['id'],enabled=False)
    b=panel('routines','Routines')
    for label,fn in [('New draft',routine),('Edit',lambda:routine(True)),('Review & enable',approve),('Disable',disable),('Run',run_routine)]:
        ttk.Button(b,text=label,command=fn).pack(side='left',padx=3)
    def schedule():
        row=need('routines')
        if not row:return
        minutes=simpledialog.askinteger('Schedule routine','Run every how many minutes while JoJo is running? (5–120)',minvalue=5,maxvalue=120,parent=window)
        if minutes and messagebox.askyesno('Approve scheduled actions',row['instructions']+'\n\nRun these actions automatically every '+str(minutes)+' minutes? Missed runs are skipped.',parent=window):call('schedule',id=row['id'],minutes=minutes)
    ttk.Button(b,text='Schedule…',command=schedule).pack(side='left',padx=3)
    def unschedule():
        row=need('schedules')
        if row:call('unschedule',id=row['routine_id'])
    b=panel('schedules','Schedules');ttk.Button(b,text='Remove schedule',command=unschedule).pack(side='left')

    def resume():
        row=need('history')
        if not row:return
        correction=simpledialog.askstring('Continue task','Correction or remaining work (blank keeps original goal):',parent=window)
        if correction is not None:call('resume',id=row['id'],text=correction)
    def actions():
        row=need('history')
        if row:call('actions',id=row['id'])
    b=panel('history','Tasks & recovery')
    ttk.Button(b,text='Inspect action history',command=actions).pack(side='left')
    ttk.Button(b,text='Continue / correct',command=resume).pack(side='left',padx=6)
    def handoff():
        row=need('history')
        if row:call('handoff',id=row['id'])
    ttk.Button(b,text='Continue on phone',command=handoff).pack(side='left')
    def feedback():
        row=need('history')
        if not row:return
        success=messagebox.askyesnocancel('Task feedback','Did JoJo complete this task correctly?',parent=window)
        if success is None:return
        note=simpledialog.askstring('Correction','Optional instruction JoJo should remember (no secrets):',parent=window)
        if note is not None:call('feedback',id=row['id'],enabled=success,text=note)
    ttk.Button(b,text='Rate / correct',command=feedback).pack(side='left',padx=6)
    def draft_from_task():
        row=need('history')
        if row:call('draft_from_task',id=row['id'],name='Recorded workflow')
    ttk.Button(b,text='Make routine draft',command=draft_from_task).pack(side='left')
    def accept_handoff():
        row=need('handoffs')
        if row and row['target']=='mobile':
            status.set('On your paired phone say: JoJo, continue laptop task. Discard extra phone handoffs first.');return
        if row and messagebox.askyesno('Accept phone context',describe('handoffs',row)+'\n\nContinue this task on the laptop?',parent=window):call('accept_handoff',id=row['id'])
    b=panel('handoffs','Handoffs');ttk.Button(b,text='Review & accept',command=accept_handoff).pack(side='left')
    ttk.Button(b,text='Discard',command=lambda:remove('handoffs','discard_handoff')).pack(side='left',padx=6)
    def permission(enabled):
        row=need('permissions')
        if row:call('temporary_permission',id=row['id'],enabled=enabled,minutes=15)
    def clear_permission():
        row=need('permissions')
        if row:call('clear_permission',id=row['id'])
    b=panel('permissions','Permissions')
    for label,fn in [('Allow 15 minutes',lambda:permission(True)),('Block 15 minutes',lambda:permission(False)),('Restore saved setting',clear_permission)]:
        ttk.Button(b,text=label,command=fn).pack(side='left',padx=3)
    def undo():
        row=need('undo')
        if row and messagebox.askyesno('Restore original file',row['path']+'\n\nRestore the version before JoJo edited this file? Changes made afterwards will block restoration.',parent=window):call('undo',id=row['id'])
    b=panel('undo','Undo files');ttk.Button(b,text='Review & restore',command=undo).pack(side='left')
    metrics=ScrolledText(tabs,wrap='word');tabs.add(metrics,text='Reliability')
    ttk.Label(window,textvariable=status,wraplength=820).pack(padx=12,pady=(0,10),anchor='w')

    def drain():
        nonlocal data,busy
        if not window.winfo_exists():return
        try:
            while True:
                kind,payload=events.get_nowait();busy=False
                if kind=='error':status.set(payload);continue
                data,result,action=payload;private.set(data['private_session'])
                for key,(listing,details) in widgets.items():
                    listing.delete(0,'end')
                    for row in data[key]:
                        label=row.get('text') or row.get('path') or row.get('name') or row.get('message') or row.get('context') or row.get('routine_id','')
                        prefix=('enabled' if row.get('enabled') else 'draft') if key=='routines' else row.get('status','')
                        listing.insert('end',(prefix+' • ' if prefix else '')+label[:130])
                report=data['metrics']
                metrics.delete('1.0','end');metrics.insert('end','Recorded task outcomes\n\n'+'\n'.join(name.replace('_',' ').capitalize()+': '+str(count) for name,count in report.get('outcomes',{}).items())
                    +'\n\nOwner-reviewed tasks: '+str(report.get('owner_reviewed_tasks',0))+'\nOwner-reported success: '+(str(round(report['owner_reported_success_fraction']*100))+'%' if report.get('owner_reported_success_fraction') is not None else 'No feedback yet')
                    +'\n\n'+report['note']+'\n\nFrequent tool failures:\n'+'\n'.join(row['tool'].replace('_',' ')+': '+str(row['failures']) for row in report.get('frequent_failures',[])))
                status.set('Saved locally.' if action else 'Workspace ready.')
                if action in ('actions','search'):
                    key='history' if action=='actions' else 'documents'
                    box=widgets[key][1];box.delete('1.0','end')
                    if action=='search':box.insert('end','\n\n'.join(row['path']+' — page '+str(row['page'])+'\n'+row['text'] for row in result.get('results',[])) or 'No matching indexed text.')
                    else:box.insert('end','\n\n'.join('Step '+str(row['step'])+' · '+row['tool'].replace('_',' ')+' · '+row['state']+'\n'+row['details'] for row in result.get('actions',[])) or 'No durable tool actions recorded for this task.')
                if action in ('resume','run_routine'):status.set('Task queued. Live progress appears in the main dashboard.')
        except queue.Empty:pass
        window.after(150,drain)
    call();drain()
