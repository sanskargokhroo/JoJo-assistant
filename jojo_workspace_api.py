"""Local native workspace API; file indexing and approvals stay on the laptop."""
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
import jojo_workspace as workspace
import queue

class Change(BaseModel):
    action: str = Field(max_length=40)
    id: str = Field(default='', max_length=150)
    text: str = Field(default='', max_length=6000)
    name: str = Field(default='', max_length=100)
    kind: str = Field(default='preference', max_length=30)
    enabled: bool = False
    minutes: int = Field(default=15,ge=1,le=120)

def local(request):
    if request.client and request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        raise HTTPException(403, 'Workspace management is local to this laptop.')

def register(app, manager, stop_speech):
    @app.get('/api/workspace')
    def snapshot(request: Request):
        local(request)
        from jojo_journal import history
        from jojo_permissions import snapshot as permissions
        from jojo_undo import history as undo_history
        from jojo_routines import schedules
        from jojo_handoff import pending
        return {'private_session': workspace.private_session(), 'cards': workspace.list_cards(),
                'documents': workspace.documents(), 'routines': workspace.routines(),
                'history': history(60), 'metrics': workspace.metrics(), 'permissions':permissions(), 'undo':undo_history(), 'schedules':schedules(), 'handoffs':pending('laptop')+pending('mobile')}

    @app.post('/api/workspace')
    def change(value: Change, request: Request):
        local(request)
        try:
            if value.action == 'privacy':
                if value.enabled:
                    with manager.lock:
                        for task in manager.tasks.values():
                            if not task.done.is_set():task.private=True
                return workspace.set_private(value.enabled)
            if value.action == 'save_memory':return {'id':workspace.save_card(value.text,value.kind,value.id)}
            if value.action == 'feedback':return workspace.task_feedback(value.id,value.enabled,value.text)
            if value.action == 'draft_from_task':
                from jojo_journal import history
                row=next((row for row in history(200) if row['id']==value.id),None)
                if not row:raise ValueError('Task not found.')
                return workspace.save_routine(value.name or 'Recorded workflow',row['message'][:6000])
            if value.action == 'temporary_permission':
                from jojo_permissions import set_temporary
                set_temporary(value.id,value.enabled,value.minutes);return {'ok':True}
            if value.action == 'clear_permission':
                from jojo_permissions import remove
                remove(value.id);return {'ok':True}
            if value.action == 'undo':
                from jojo_undo import restore
                return restore(value.id)
            if value.action == 'schedule':
                from jojo_routines import schedule
                schedule(value.id,value.minutes);return {'ok':True}
            if value.action == 'handoff':
                from jojo_journal import history
                from jojo_handoff import create
                row=next((row for row in history(200) if row['id']==value.id),None)
                if not row or row['source']!='laptop':raise ValueError('Select a laptop conversation.')
                return create('laptop','mobile',row['message'],row['reply'])
            if value.action == 'accept_handoff':
                from jojo_handoff import take
                return manager.submit(take(value.id,'laptop'),'laptop',False)
            if value.action == 'discard_handoff':
                from jojo_handoff import discard
                discard(value.id);return {'ok':True}
            if value.action == 'unschedule':
                from jojo_routines import unschedule
                unschedule(value.id);return {'ok':True}
            if value.action == 'delete_memory':workspace.delete_card(value.id)
            elif value.action == 'index_document':
                from jojo_capabilities import enabled
                if not enabled('files'):raise ValueError('File access is disabled.')
                return workspace.index_document(value.text)
            elif value.action == 'delete_document':workspace.delete_document(value.id)
            elif value.action == 'search':return workspace.search_knowledge(value.text)
            elif value.action == 'save_routine':return workspace.save_routine(value.name,value.text,value.id)
            elif value.action == 'enable_routine':workspace.enable_routine(value.id,value.enabled)
            elif value.action == 'run_routine':return manager.submit(workspace.routine_prompt(value.id),'laptop',False)
            elif value.action == 'resume':
                old = manager.get(value.id)
                if old and old['status'] not in ('failed','incomplete','cancelled','needs_input'):
                    raise ValueError('Stop this task and wait for it to finish before resuming.')
                return manager.submit(workspace.resume_prompt(value.id,value.text),'laptop',False)
            elif value.action == 'actions':return {'actions':workspace.task_actions(value.id)}
            elif value.action != 'delete_memory':raise ValueError('Unknown workspace action.')
            return {'ok':True}
        except queue.Full:
            raise HTTPException(429,'Task queue is full. Wait for the current work to finish.')
        except (ValueError, OSError, PermissionError) as exc:
            raise HTTPException(400,str(exc))
