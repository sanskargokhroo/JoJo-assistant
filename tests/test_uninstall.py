"""Non-destructive tests: no real process, Startup entry, Firebase or file deletion."""
import queue
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import jojo_uninstall as uninstall
from jojo_uninstall_cloud import erase_collection, erase, LEGACY

class UninstallTests(unittest.TestCase):
    def test_refuses_unrecognized_or_system_root(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):uninstall.validate_root(Path(temp))
        with self.assertRaises(ValueError):uninstall.validate_root(Path.cwd().anchor)

    def test_install_markers_required_and_junction_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            for name in ('jojo_core.py','jojo_desktop.py','jojo_start.py','jojo_uninstall.ps1'):(root/name).touch()
            self.assertEqual(uninstall.validate_root(root),root)
            with patch.object(Path,'is_junction',return_value=True):
                with self.assertRaises(ValueError):uninstall.validate_root(root)

    def test_changed_plan_cannot_launch_helper(self):
        with patch.object(uninstall,'removal_plan',return_value={'root':'new'}), patch.object(uninstall.subprocess,'Popen') as process:
            with self.assertRaises(ValueError):uninstall.launch({'root':'old'},False)
            process.assert_not_called()

    def test_external_data_folder_is_not_recursively_deleted(self):
        import jojo_config
        with patch.object(jojo_config,'DATA_DIR',Path.cwd().parent),patch.object(uninstall,'validate_root',return_value=Path.cwd()):
            with self.assertRaisesRegex(ValueError,'outside'):uninstall.removal_plan()

    def test_nested_cloud_records_deleted_before_parent(self):
        events=[];parent=Mock();child=Mock();doc=Mock();nested=Mock()
        parent.limit.return_value.stream.side_effect=[[doc],[]]
        child.limit.return_value.stream.side_effect=[[nested],[]]
        doc.reference.collections.return_value=[child];nested.reference.collections.return_value=[]
        nested.reference.delete.side_effect=lambda **kw:events.append('child')
        doc.reference.delete.side_effect=lambda **kw:events.append('parent')
        erase_collection(parent)
        self.assertEqual(events,['child','parent'])

    def test_cloud_failure_propagates_instead_of_reporting_success(self):
        collection=Mock();collection.limit.return_value.stream.side_effect=TimeoutError
        with self.assertRaises(TimeoutError):erase_collection(collection)

    def test_cloud_erase_is_scoped_not_project_wide(self):
        client=Mock();shared=client.collection.return_value.document.return_value
        shared.collections.return_value=[]
        with patch('jojo_uninstall_cloud.erase_collection'):
            erase(client,'primary')
        self.assertEqual([c.args[0] for c in client.collection.call_args_list],['jojo_memory',*LEGACY])
        client.collection.return_value.document.assert_called_once_with('primary')

    def test_stop_bypasses_command_queue_and_disables_restart(self):
        from jojo_desktop import JoJoDesktop
        desktop=JoJoDesktop.__new__(JoJoDesktop)
        desktop.stopping=False;desktop.launch_core=True;desktop.detail=Mock();desktop.ambient=Mock()
        desktop.events=queue.Queue();desktop.requests=Mock()
        with patch('jojo_desktop.request',return_value={'status':'shutting_down'}) as api,patch('jojo_desktop.threading.Thread') as thread:
            desktop.stop_assistant();thread.call_args.kwargs['target']()
            desktop.stop_assistant()
        api.assert_called_once_with('/api/shutdown',{},timeout=5)
        desktop.requests.put.assert_not_called()
        self.assertFalse(desktop.launch_core)
        self.assertEqual(desktop.events.get()[0],'shutdown')

if __name__=='__main__':unittest.main()
