from jojo_config import api_keys, make_client, MODEL, DATA_DIR
"""
👁️ JoJo Vision Click & GUI Automation Engine
Gives JoJo complete, autonomous control over the Windows desktop:
- Screen capture via winsta0/default interactive desktop hooks
- Gemini 3.6 Flash Visual Grounding (locates any button, menu, toggle, text)
- Mouse control: smooth move, left click, double click, right click, scroll, drag
- Keyboard control: hotkeys, individual keys (Enter, Tab, Space, Esc, Backspace)
- Instant text typing via clipboard paste (works for English & Hindi Unicode)
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles to prevent charmap UnicodeEncodeError
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import time
import json
import ctypes
import re
from ctypes import wintypes
from PIL import Image, ImageGrab
import pyautogui
pyautogui.FAILSAFE = True

try:
    import pyperclip
except ImportError:
    pyperclip = None

from google import genai
from google.genai import types

# Shared Gemini API Keys (rotates automatically on quota or error)
GEMINI_KEYS = api_keys()

_current_key_index = 0

def get_gemini_client():
    global _current_key_index
    key = GEMINI_KEYS[_current_key_index]
    return make_client(api_key=key)

def rotate_gemini_key():
    global _current_key_index
    _current_key_index = (_current_key_index + 1) % max(1, len(GEMINI_KEYS))
    print(f"🔄 Rotated Gemini Vision Key to index: {_current_key_index}")

def ensure_desktop_access():
    """Ensure process thread is attached to interactive desktop (winsta0\\default)."""
    try:
        user32 = ctypes.windll.user32
        user32.OpenWindowStationW.restype = wintypes.HANDLE
        user32.OpenWindowStationW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL, wintypes.DWORD]
        user32.SetProcessWindowStation.restype = wintypes.BOOL
        user32.SetProcessWindowStation.argtypes = [wintypes.HANDLE]
        user32.OpenDesktopW.restype = wintypes.HANDLE
        user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]

        hwinsta = user32.OpenWindowStationW('winsta0', False, 0x000F037F)
        if hwinsta:
            user32.SetProcessWindowStation(hwinsta)
        hdesk = user32.OpenDesktopW('default', 0, False, 0x000F01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception as e:
        pass

def take_screenshot(save_path=None):
    """Safely captures full screen regardless of session or service context."""
    from jojo_policy import guard_desktop
    guard_desktop('')
    from jojo_desktop_guard import guard_capture
    guard_capture()
    ensure_desktop_access()
    im = None
    try:
        im = ImageGrab.grab()
    except Exception:
        try:
            im = pyautogui.screenshot()
        except Exception:
            try:
                import mss
                with mss.MSS() as sct:
                    mon = sct.monitors[1]
                    sct_img = sct.grab(mon)
                    im = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
            except Exception as e:
                print(f"⚠️ Screenshot capture failed: {e}")
                return None

    if im and save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        im.save(save_path)
    return im

def ai_locate_element_on_screen(target_name):
    """
    Takes a real screenshot and uses Gemini 3.6 Flash Vision to find the exact (x, y) coordinates
    of the target element (button, toggle, menu item, text, icon).
    Returns dict: {'found': bool, 'x': int, 'y': int, 'element_name': str, 'confidence': float}
    """
    ensure_desktop_access()
    im = take_screenshot()
    if not im:
        return {"found": False, "error": "Screen capture failed"}

    width, height = im.size

    # Save to compressed in-memory or temp JPEG for ultra-fast upload
    tmp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "vision_temp.jpg")
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
    im.save(tmp_path, format="JPEG", quality=85)

    try:
        with open(tmp_path, "rb") as f:
            img_bytes = f.read()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    prompt = f"""You are an ultra-precise GUI automation agent.
Screen resolution: {width} width by {height} height.
Locate the UI element matching: "{target_name}".
It could be a button, toggle switch, tab, menu option, link, icon, checkbox, or labeled setting on screen.
Find the center of this element so a mouse click will successfully trigger it.
Return ONLY valid JSON:
{{
  "found": true or false,
  "x": center_x_integer_between_0_and_{width},
  "y": center_y_integer_between_0_and_{height},
  "element_name": "what was matched on screen",
  "confidence": 0.0_to_1.0
}}"""

    attempts = 0
    while attempts < min(3, len(GEMINI_KEYS)):
        try:
            client = get_gemini_client()
            chat = client.chats.create(
                model=MODEL,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            resp = chat.send_message([
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                prompt
            ])
            text = resp.text.strip()
            # Clean possible markdown block
            text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)
            return data
        except Exception as e:
            print(f"⚠️ Gemini Vision locator error: {e}")
            rotate_gemini_key()
            attempts += 1

    return {"found": False, "error": "AI Vision locator quota/network error"}

def ai_click_element(target_name, action="click"):
    """
    Autonomous AI Click:
    1. Scans screen for target_name
    2. Moves mouse to element center
    3. Performs click (left, double, right)
    Returns: (success: bool, message: str)
    """
    from jojo_policy import guard_desktop
    guard_desktop(target_name)
    ensure_desktop_access()
    print(f"👁️ JoJo AGI Vision searching for: '{target_name}'...")
    data = ai_locate_element_on_screen(target_name)

    if not data or not data.get("found"):
        desc = data.get("error", "Element not visible")
        print(f"⚠️ AI Vision could not find '{target_name}': {desc}")
        return False, f"बॉस, स्क्रीन पर '{target_name}' नहीं दिख रहा है!"

    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    elem_name = data.get("element_name", target_name)
    conf = data.get("confidence", 1.0)

    print(f"🎯 AI Vision found '{elem_name}' at ({x}, {y}) [Confidence: {conf}]")

    # Smooth mouse movement
    try:
        from jojo_desktop_guard import guard_point
        guard_desktop(elem_name)
        guard_point(x,y)
        pyautogui.moveTo(x, y, duration=0.35, tween=pyautogui.easeInOutQuad)
        time.sleep(0.08)

        if action == "double" or action == "double_click":
            pyautogui.doubleClick(x, y)
            act_desc = "डबल क्लिक"
        elif action == "right" or action == "right_click":
            pyautogui.rightClick(x, y)
            act_desc = "राइट क्लिक"
        else:
            pyautogui.click(x, y)
            act_desc = "क्लिक"

        return True, f"हाँ बॉस! '{elem_name}' पर {act_desc} कर दिया!"
    except Exception as e:
        print(f"⚠️ Mouse action failed: {e}")
        return False, f"बॉस, क्लिक करने में कुछ दिक्कत आई: {e}"

def type_text(text_to_type):
    """Types any text (English or Hindi Unicode) safely via clipboard paste."""
    from jojo_policy import guard_desktop
    guard_desktop(text_to_type)
    from jojo_desktop_guard import guard_focus
    guard_focus()
    ensure_desktop_access()
    try:
        if pyperclip:
            pyperclip.copy(text_to_type)
            time.sleep(0.05)
            pyautogui.hotkey('ctrl', 'v')
            return True, f"'{text_to_type}' टाइप कर दिया बॉस!"
        else:
            pyautogui.write(text_to_type, interval=0.03)
            return True, f"'{text_to_type}' टाइप कर दिया बॉस!"
    except Exception as e:
        print(f"⚠️ Type text failed: {e}")
        return False, f"टाइप करने में समस्या आई: {e}"

def press_keyboard_key(key_name):
    """Presses specific keyboard key or combo."""
    from jojo_policy import guard_desktop
    guard_desktop(key_name)
    from jojo_desktop_guard import guard_focus
    guard_focus()
    ensure_desktop_access()
    key = key_name.lower().strip()
    key_map = {
        "enter": "enter",
        "tab": "tab",
        "space": "space",
        "esc": "escape",
        "escape": "escape",
        "backspace": "backspace",
        "delete": "delete",
        "up": "up",
        "down": "down",
        "left": "left",
        "right": "right",
        "win": "win",
        "windows": "win"
    }

    try:
        if key in key_map:
            pyautogui.press(key_map[key])
            return True, f"{key.upper()} बटन दबा दिया बॉस!"
        elif "+" in key:
            parts = [p.strip() for p in key.split("+")]
            pyautogui.hotkey(*parts)
            return True, f"{key.upper()} शॉर्टकट दबा दिया बॉस!"
        else:
            pyautogui.press(key)
            return True, f"{key} दबा दिया बॉस!"
    except Exception as e:
        return False, f"कीबोर्ड एक्शन विफल: {e}"

def take_and_save_screenshot():
    """Takes a full desktop screenshot and saves to Desktop."""
    ensure_desktop_access()
    try:
        desktop_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        main_path = os.path.join(desktop_dir, "jojo_screenshot.png")
        ts_path = os.path.join(desktop_dir, f"screenshot_{timestamp}.png")

        im = take_screenshot()
        if im:
            im.save(main_path)
            im.save(ts_path)
            print(f"📸 Screenshot saved to: {main_path}")
            return True, "स्क्रीनशॉट डेस्कटॉप पर सेव कर दिया बॉस! 📸"
        else:
            return False, "बॉस, स्क्रीनशॉट लेने में दिक्कत आई!"
    except Exception as e:
        print(f"⚠️ Screenshot error: {e}")
        return False, f"स्क्रीनशॉट एरर: {e}"
