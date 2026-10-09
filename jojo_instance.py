"""Process lifetime mutexes for the Windows core and desktop window."""
import ctypes
import sys

_handles = []

def claim_instance(name):
    if sys.platform != 'win32':
        return True
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, False, 'Local\\JoJo.' + name)
    error = ctypes.get_last_error()
    if not handle:
        raise OSError(error, 'Cannot create JoJo instance mutex')
    if error == 183:
        kernel.CloseHandle(handle)
        return False
    _handles.append(handle)
    return True
