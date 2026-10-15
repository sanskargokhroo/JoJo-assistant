import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from jojo_controls import terminate_backend


class ProcessLookupTests(unittest.TestCase):
    def test_inaccessible_unrelated_and_exited_processes_are_not_killed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            cases=[('python.exe',None,True),('python.exe',['python.exe',str(root/'other.py')],True),
                   ('other.exe',['other.exe',str(root/'jojo_core.py')],True),
                   ('python.exe',['python.exe',str(root/'jojo_core.py')],False),
                   ('python.exe',['python.exe',str(root/'jojo_core.py')],True)]
            processes=[]
            for pid,(name,args,running) in enumerate(cases,100):
                process=Mock(pid=pid,info={'name':name,'cmdline':args})
                process.is_running.return_value=running;processes.append(process)
            with patch('psutil.process_iter',return_value=processes),patch('subprocess.run') as run:
                terminate_backend(root)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0],['taskkill.exe','/PID','104','/T','/F'])
