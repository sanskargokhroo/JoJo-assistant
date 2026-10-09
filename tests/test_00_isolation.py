"""Install test storage BEFORE discovery imports any JoJo configuration modules.

Filename ordering is intentional for unittest discovery. Do not use real owner
credentials, preferences, journal or workspace databases in regression tests.
"""
import atexit
import os
import tempfile

_state=tempfile.TemporaryDirectory(prefix='jojo-suite-')
os.environ['JOJO_DATA_DIR']=_state.name
os.environ['JOJO_DISABLE_CLOUD']='1'
os.environ['JOJO_NO_OVERLAY']='1'
os.environ['JOJO_DISABLE_SECURITY_MONITOR']='1'
atexit.register(_state.cleanup)
