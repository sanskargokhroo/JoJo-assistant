"""Local UI Automation payment/credential checks; never read field values.

Run COM work on a bounded daemon so an unresponsive app cannot hang JoJo's task.
Unlabelled/custom controls still need manual handling; this is not a sandbox.
"""
import queue
import threading
import re
from jojo_policy import payment_surface, blocked_reason, PAYMENT_HANDOFF

_requests = queue.Queue(maxsize=1)
_thread = None
_lock = threading.Lock()

def sensitive_label(name, password=False):
    return password or bool(re.search(r'\b(card number|cvv|expiry date|upi pin|enter otp|one.time password)\b|कार्ड नंबर|ओटीपी', name, re.I)) or name.strip().casefold() in {
        'checkout', 'secure checkout', 'payment', 'payment method', 'payment options',
        'select payment method', 'भुगतान', 'पेमेंट'}

def _inspect(mode, point):
    from pywinauto.uia_element_info import UIAElementInfo
    from pywinauto.uia_defines import IUIA
    if mode == 'screen':
        import ctypes
        user=ctypes.windll.user32;user.GetForegroundWindow.restype=ctypes.c_void_p
        root=UIAElementInfo(user.GetForegroundWindow())
        pending=[(root,0)];visited=0
        while pending and visited<400:
            node,depth=pending.pop();visited+=1
            if not node.visible:continue
            if sensitive_label(node.name or '', bool(node.element.CurrentIsPassword)) or (node.control_type == 'Header' and payment_surface(node.name or '')):
                return True
            if depth<16:pending.extend((child,depth+1) for child in node.children()[:100])
        return False
    node=UIAElementInfo.from_point(*point) if mode=='point' else UIAElementInfo(IUIA().get_focused_element())
    if node is None:raise RuntimeError('No accessible target')
    labelled=False
    for depth in range(4):
        if node is None:break
        name=node.name or ''
        if bool(node.element.CurrentIsPassword) or payment_surface(name) or blocked_reason(name):return True
        # Window/document titles do not identify an otherwise unlabelled button.
        if name.strip() and node.control_type not in ('Window','Pane','Document'):labelled=True
        node=node.parent
    if mode=='point' and not labelled:raise RuntimeError('Target has no accessible label')
    return False

def _run():
    import comtypes
    comtypes.CoInitialize()
    try:
        while True:
            mode,point,result=_requests.get()
            try:result.put((_inspect(mode,point),None))
            except Exception as exc:result.put((False,type(exc).__name__))
    finally:comtypes.CoUninitialize()

def _probe(mode,point=None):
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread=threading.Thread(target=_run,name='JoJo local UI safety',daemon=True);_thread.start()
    result=queue.Queue(maxsize=1)
    try:
        _requests.put_nowait((mode,point,result))
        blocked,error=result.get(timeout=2)
    except (queue.Full,queue.Empty) as exc:
        raise PermissionError('Screen safety check unavailable. Is step ko manually kijiye.') from exc
    if error:raise PermissionError('Screen target verify nahi hua; is step ko manually kijiye.')
    if blocked:raise PermissionError(PAYMENT_HANDOFF)

def guard_capture(): _probe('screen')
def guard_focus(): _probe('focus')
def guard_point(x,y): _probe('point',(int(x),int(y)))
