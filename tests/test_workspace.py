"""Behavioral tests with synthetic documents, commands and isolated private storage."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import test_00_isolation  # Configure storage before importing application modules.


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        import jojo_workspace as ws
        import jojo_config as config
        import jojo_journal as journal
        self.ws=ws;self.journal=journal
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for module in (ws,config,journal):self.stack.enter_context(patch.object(module,'DATA_DIR',self.root))
        self.stack.enter_context(patch('jojo_cloud_memory.enqueue'))
        self.stack.enter_context(patch('jojo_cloud_memory.queue_delete'))

    def test_memory_edit_delete_and_privacy(self):
        identifier=self.ws.save_card('Use concise replies')
        self.ws.save_card('Use detailed replies',identifier=identifier)
        self.assertEqual(len(self.ws.list_cards()),1)
        self.assertIn('detailed',self.ws.card_context())
        self.ws.set_private(True)
        self.assertEqual(self.ws.card_context(),'')
        with self.assertRaises(ValueError):self.ws.save_card('Do not retain this')
        self.ws.delete_card(identifier)
        self.assertEqual(self.ws.list_cards(),[])

    def test_knowledge_only_indexes_selected_file_and_removes(self):
        selected=self.root/'chosen.txt';selected.write_text('Saturn has rings. Research notes.',encoding='utf-8')
        (self.root/'unselected.txt').write_text('private unselected content')
        item=self.ws.index_document(str(selected))
        results=self.ws.search_knowledge('Saturn')['results']
        self.assertEqual(results[0]['path'],str(selected.resolve()))
        self.assertEqual(results[0]['page'],1)
        self.assertEqual(self.ws.search_knowledge('unselected')['results'],[])
        self.ws.delete_document(item['id'])
        self.assertTrue(selected.exists())
        self.assertEqual(self.ws.search_knowledge('Saturn')['results'],[])

    def test_routine_edit_revokes_approval(self):
        item=self.ws.save_routine('Work mode','Open Notepad')
        with self.assertRaises(ValueError):self.ws.routine_prompt(item['id'])
        self.ws.enable_routine(item['id'],True)
        self.assertIn('Notepad',self.ws.routine_prompt(item['id']))
        self.ws.save_routine('Work mode','Open Calculator',item['id'])
        with self.assertRaises(ValueError):self.ws.routine_prompt(item['id'])

    def test_resume_uses_saved_actions_without_executing_them(self):
        self.journal.record({'id':'x','source':'laptop','message':'Write a note','reply':'Interrupted','status':'incomplete','events':[]})
        with self.ws.connect() as db:
            db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?)',('x',1,'write_local_file','started','result unknown',1))
        prompt=self.ws.resume_prompt('x','Use the corrected title')
        self.assertIn('result unknown',prompt)
        self.assertIn('never repeat',prompt.casefold())
        self.assertIn('corrected title',prompt)
        self.assertEqual(self.ws.task_actions('x')[0]['state'],'started')

    def test_long_action_history_resumes_with_all_step_statuses(self):
        self.journal.record({'id':'long','source':'laptop','message':'Finish the fixture','reply':'Need more work','status':'incomplete'})
        with self.ws.connect() as db:
            for step in range(1,25):db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?)',('long',step,'fixture','started' if step==24 else 'returned','x'*4000,step))
        prompt=self.ws.resume_prompt('long','Use the corrected title')
        self.assertLessEqual(len(prompt),12000)
        payload=json.loads(prompt.split('\n',1)[1])
        self.assertEqual(len(payload['actions']),24)
        self.assertEqual(payload['actions'][-1]['state'],'started')
        self.assertTrue(payload['actions'][-1]['truncated'])
        self.assertEqual(payload['original_request'],'Finish the fixture')

    def test_private_task_remains_private_after_toggle_off(self):
        from jojo_runtime import TaskManager,report_progress
        self.ws.set_private(True)
        def handle(message,source):
            self.ws.set_private(False)
            report_progress('private progress')
            self.ws.action_event(1,'fixture','returned','private output')
            return 'private reply'
        manager=TaskManager(handle,journal=self.journal.record)
        self.assertEqual(manager.run_sync('private input'),'private reply')
        self.assertEqual(self.journal.history(),[])
        with self.ws.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM actions').fetchone()[0],0)

    def test_action_started_and_progress_persist_before_completion(self):
        from jojo_runtime import TaskManager,report_progress
        entered=threading.Event();release=threading.Event()
        def handle(message,source):
            self.ws.action_event(1,'fixture','started','intent')
            report_progress('Waiting for fixture')
            entered.set();release.wait(3);return 'done'
        manager=TaskManager(handle,journal=self.journal.record)
        task=manager.submit('fixture')
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(self.journal.history()[0]['status'],'running')
            self.assertEqual(self.ws.task_actions(task['id'])[0]['state'],'started')
        finally:
            release.set();manager.tasks[task['id']].done.wait(3)

    def test_workspace_api_rejects_remote_management(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from jojo_workspace_api import register
        from jojo_runtime import TaskManager
        app=FastAPI();register(app,TaskManager(lambda message,source:'ok'),lambda:None)
        api=TestClient(app,client=('203.0.113.10',40000))
        self.assertEqual(api.get('/api/workspace').status_code,403)

    def test_schedules_run_once_and_edit_removes_schedule(self):
        from jojo_routines import schedule,run_due,schedules
        from unittest.mock import Mock
        item=self.ws.save_routine('Fixture','Check local time')
        self.ws.enable_routine(item['id'],True);schedule(item['id'],5)
        with self.ws.connect() as db:db.execute('UPDATE schedules SET next_run=0')
        manager=Mock();manager.get.return_value=None;manager.submit.return_value={'id':'one'}
        run_due(manager);run_due(manager)
        self.assertEqual(manager.submit.call_count,1)
        self.ws.save_routine('Changed fixture','Check battery',item['id'])
        self.assertEqual(schedules(),[])

    def test_private_session_skips_scheduled_run(self):
        from jojo_routines import schedule,run_due
        from unittest.mock import Mock
        item=self.ws.save_routine('Fixture','Check local time')
        self.ws.enable_routine(item['id'],True);schedule(item['id'],5)
        with self.ws.connect() as db:db.execute('UPDATE schedules SET next_run=0')
        self.ws.set_private(True);manager=Mock();run_due(manager)
        manager.submit.assert_not_called()

    def test_temporary_permissions_expire(self):
        import jojo_permissions as permissions
        try:
            with patch.object(permissions.time,'monotonic',return_value=100):permissions.set_temporary('files',False,1)
            with patch.object(permissions.time,'monotonic',return_value=110):self.assertFalse(permissions.effective('files',True))
            with patch.object(permissions.time,'monotonic',return_value=161):self.assertTrue(permissions.effective('files',True))
        finally:permissions.remove('files')

    def test_handoff_bound_to_destination_and_consumed_once(self):
        from jojo_handoff import create,take,pending
        item=create('laptop','mobile','Read my document','File not yet copied')
        with self.assertRaises(ValueError):take(item['id'],'laptop')
        self.assertEqual(len(pending('mobile')),1)
        self.assertIn('File not yet copied',take(item['id'],'mobile'))
        with self.assertRaises(ValueError):take(item['id'],'mobile')

    def test_handoff_survives_full_queue(self):
        from jojo_handoff import create,accept,pending
        from unittest.mock import Mock
        import queue
        item=create('mobile','laptop','Continue the fixture')
        consumer=Mock(side_effect=queue.Full)
        with self.assertRaises(queue.Full):accept(item['id'],'laptop',consumer)
        self.assertEqual(len(pending('laptop')),1)
        self.assertEqual(accept(item['id'],'laptop',lambda prompt:{'id':'accepted'}),{'id':'accepted'})
        self.assertEqual(pending('laptop'),[])

    def test_private_mode_cannot_consume_saved_handoff(self):
        from jojo_handoff import create,take,pending
        item=create('laptop','mobile','Private fixture context')
        self.ws.set_private(True)
        with self.assertRaises(ValueError):take(item['id'],'mobile')
        self.assertEqual(len(pending('mobile')),1)

    def test_retried_request_survives_restart_without_reexecution(self):
        from jojo_runtime import TaskManager
        from unittest.mock import Mock
        handler=Mock(return_value='done')
        manager=TaskManager(handler,journal=self.journal.record,lookup=self.journal.task_record)
        first=manager.submit('Fixture','laptop',False,request_id='fixture-stable')
        self.assertTrue(manager.tasks[first['id']].done.wait(3))
        retry=manager.submit('Fixture','laptop',False,request_id='fixture-stable')
        self.assertEqual(first['id'],retry['id']);self.assertEqual(handler.call_count,1)
        restarted=TaskManager(handler,journal=self.journal.record,lookup=self.journal.task_record)
        recovered=restarted.submit('Fixture','laptop',False,request_id='fixture-stable')
        self.assertEqual(recovered['status'],'completed');self.assertEqual(handler.call_count,1)
        self.assertIsNone(restarted.worker)
        with self.assertRaises(ValueError):restarted.submit('Changed request',request_id='fixture-stable')
        with self.assertRaises(ValueError):restarted.submit('Fixture','mobile',request_id='fixture-stable')

    def test_duplicate_request_while_running_is_not_enqueued_twice(self):
        from jojo_runtime import TaskManager
        release=threading.Event();entered=threading.Event();calls=[]
        def handle(message,source):calls.append(message);entered.set();release.wait(3);return 'done'
        manager=TaskManager(handle)
        first=manager.submit('Fixture',request_id='in-flight')
        try:
            self.assertTrue(entered.wait(2))
            duplicate=manager.submit('Fixture',request_id='in-flight')
            self.assertEqual(first['id'],duplicate['id']);self.assertEqual(manager.queue.qsize(),0)
        finally:release.set();manager.tasks[first['id']].done.wait(3)
        self.assertEqual(calls,['Fixture'])

    def test_worker_binds_device_before_calling_handler(self):
        from jojo_runtime import TaskManager,target_platform
        observed=[]
        def handle(message,source):observed.append(target_platform());return 'done'
        manager=TaskManager(handle)
        manager.run_sync('Phone fixture','mobile');manager.run_sync('Laptop fixture','laptop')
        self.assertEqual(observed,['mobile','desktop'])

    def test_document_search_does_not_cross_device_context(self):
        self.journal.record({'id':'l','source':'laptop','message':'Laptop fixture','reply':'ok','status':'completed'})
        self.journal.record({'id':'m','source':'mobile','message':'Phone fixture','reply':'ok','status':'completed'})
        self.assertNotIn('Laptop fixture',self.journal.recall(source='mobile'))

    @unittest.skipUnless(__import__('os').name=='nt','Windows encrypted undo')
    def test_undo_encrypts_original_and_preserves_newer_edits(self):
        from jojo_undo import write_text,restore
        path=self.root/'note.txt';path.write_text('original private text',encoding='utf-8')
        item=write_text(path,'new version')
        with self.ws.connect() as db:
            row=db.execute('SELECT original FROM undo_edits').fetchone()
            self.assertNotIn(b'original private text',row['original'])
        path.write_text('user edited afterwards',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed'):restore(item['undo_id'])
        self.assertEqual(path.read_text(),'user edited afterwards')
        path.write_text('new version',encoding='utf-8')
        self.assertTrue(restore(item['undo_id'])['verified'])
        self.assertEqual(path.read_text(),'original private text')

    def test_history_clear_removes_action_and_feedback_copies(self):
        self.journal.record({'id':'clear-me','source':'laptop','message':'Fixture','reply':'Done','status':'completed'})
        self.ws.task_feedback('clear-me',False,'Prefer a smaller response')
        with self.ws.connect() as db:db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?)',('clear-me',1,'fixture','returned','old result',1))
        self.journal.clear()
        self.assertEqual(self.ws.task_actions('clear-me'),[])
        self.assertEqual(self.ws.list_cards(),[])


class MobileWorkspaceTests(unittest.TestCase):
    # Reuse isolated storage without inheriting duplicate test methods.
    def setUp(self):
        WorkspaceTests.setUp(self)
        import test_mobile_actions as base
        base.CompanionFlowTests.setUp(self)

    def voice(self,*args,**kwargs):
        import test_mobile_actions as base
        return base.CompanionFlowTests.voice(self,*args,**kwargs)

    def step(self,*args,**kwargs):
        import test_mobile_actions as base
        return base.CompanionFlowTests.step(self,*args,**kwargs)

    def test_notifications_only_requested_after_owner_verification(self):
        self.core.verify_boss.return_value=False
        self.assertNotIn('action',self.voice('JoJo notifications').json())
        self.core.verify_boss.return_value=True
        result=self.voice('JoJo notifications').json()
        self.assertTrue(result['action']['notifications'])
        with patch('jojo_android.make_client') as model:
            reply=self.step(result['session'],notifications='[{"package":"com.whatsapp","title":"Fixture","text":"Hello"}]').json()['reply']
        self.assertIn('Hello',reply);model.assert_not_called()

    def test_phone_handoff_does_not_execute_on_laptop(self):
        from jojo_handoff import create,pending
        create('laptop','mobile','Open Calculator')
        with patch('jojo_android.make_client') as model:
            result=self.voice('JoJo continue laptop task').json()
        self.assertEqual(result['action']['type'],'observe')
        self.assertEqual(pending('mobile'),[]);model.assert_not_called()


class VerificationTests(unittest.TestCase):
    def test_file_write_needs_read_observation(self):
        from test_reliability import response,AgentTests
        from jojo_agent_loop import run_tool_loop
        called=[]
        def write_local_file(file_path:str,content:str):called.append('write');return 'written'
        def read_local_file(file_path:str):called.append('read');return 'hello'
        client=AgentTests().client([
            response(('write_local_file',{'file_path':'a.txt','content':'hello'})),
            response(('finish_task',{'summary':'done','evidence_steps':[1]})),
            response(('read_local_file',{'file_path':'a.txt'})),
            response(('finish_task',{'summary':'observed','evidence_steps':[2]}))])
        self.assertEqual(run_tool_loop(client,'write hello','',[write_local_file,read_local_file]).reply,'observed')
        self.assertEqual(called,['write','read'])

    def test_duplicate_mutation_is_not_retried_without_observation(self):
        from test_reliability import response,AgentTests
        from jojo_agent_loop import run_tool_loop
        called=[]
        def type_into_active_window(text:str):called.append(text);return 'typed'
        client=AgentTests().client([response(('type_into_active_window',{'text':'hello'})),
            response(('type_into_active_window',{'text':'hello'})),
            response(('finish_task',{'summary':'Cannot verify','status':'incomplete','evidence_steps':[]}))])
        run_tool_loop(client,'type hello','',[type_into_active_window])
        self.assertEqual(called,['hello'])

    def test_notifications_dedupe_and_redact_sensitive(self):
        from jojo_notifications import summarize_notifications
        safe={'package':'com.whatsapp','title':'Fixture contact','text':'Meeting at 5'}
        raw=json.dumps([safe,safe,dict(safe,text='OTP 123456'),dict(safe,package='net.one97.paytm')])
        result=summarize_notifications(raw)
        self.assertEqual(result.count('Meeting at 5'),1)
        self.assertNotIn('123456',result)
        self.assertNotIn('paytm',result)

if __name__=='__main__':unittest.main()
