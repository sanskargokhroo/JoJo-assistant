"""Explicit current-screen clicks. No Run dialog, URI or application launch fallback."""
import re

def visible_target(message):
    value=message.casefold().strip()
    if not re.search(r'\b(click|tap|select)\b|क्लिक|दबाओ|चुनो',value):
        return None
    for label,aliases in [('Installed apps',('installed apps','installed pps','इंस्टॉल्ड ऐप्स')),
                          ('Bluetooth',('bluetooth','ब्लूटूथ'))]:
        if any(a in value for a in aliases): return label
    match=re.fullmatch(r'(?:click on|tap on|select)\s+(.+?)(?:\s+please)?',value)
    return match.group(1).strip() if match else None

def click_visible(label):
    from jojo_runtime import checkpoint
    from jojo_policy import guard_desktop
    from jojo_desktop_guard import guard_point
    checkpoint()
    guard_desktop(label)
    import ctypes
    from pywinauto import Desktop
    hwnd=ctypes.windll.user32.GetForegroundWindow()
    window=Desktop(backend='uia').window(handle=hwnd)
    controls=window.descendants()
    candidates=[c for c in controls if c.window_text().strip().casefold()==label.casefold()
                and c.is_visible() and c.is_enabled()]
    # Multiple wrappers at the exact same rectangle represent the same element.
    unique={}
    for control in candidates:
        rect=control.rectangle()
        unique[(rect.left,rect.top,rect.right,rect.bottom)]=control
    if len(unique)>1:
        return False, f'{label} ke multiple visible options hain. Exact option select kijiye.'
    if unique:
        control=next(iter(unique.values()))
        rect=control.rectangle()
        checkpoint()
        if ctypes.windll.user32.GetForegroundWindow()!=hwnd:
            return False,'Window badal gayi; click nahi kiya. Dobara boliye.'
        guard_point((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
        control.click_input()
        return True,f'Visible {label} option par click kiya. Ab kya check karna hai?'
    # Vision locates this exact label on the current screen only.
    import jojo_vision_click
    checkpoint()
    return jojo_vision_click.ai_click_element(label)
