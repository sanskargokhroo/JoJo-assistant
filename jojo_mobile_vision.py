from jojo_config import api_keys, make_client, MODEL, DATA_DIR
"""
📱 JoJo Mobile AI Vision Click Engine
Autonomous Visual Grounding & Touch Automation for Android:
- Works natively on Android (Termux) via `screencap` and `input tap/swipe/keyevent`
- Works from PC via ADB (USB / Wireless ADB)
- Uses Gemini 3.6 Flash Visual Grounding to locate buttons, toggles, permissions & settings
- Supports Allow / Deny dialogs, Bluetooth device select, Wi-Fi, scrolling & typing
"""

import os
import sys

# Ensure UTF-8 output
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
import subprocess
import shutil
import re
from PIL import Image
import io

from google import genai
from google.genai import types

# Shared Gemini API Keys
GEMINI_KEYS = api_keys()

_gemini_key_idx = 0

def get_gemini_client():
    global _gemini_key_idx
    key = GEMINI_KEYS[_gemini_key_idx]
    return make_client(api_key=key)

def rotate_gemini_key():
    global _gemini_key_idx
    _gemini_key_idx = (_gemini_key_idx + 1) % max(1, len(GEMINI_KEYS))

def is_android_device():
    """Checks if running directly inside Termux on Android."""
    return bool(os.environ.get("PREFIX") and "termux" in os.environ.get("PREFIX", "").lower()) or os.path.exists("/system/bin/input")

def get_adb_executable():
    """Finds ADB on PC."""
    candidates = [
        shutil.which("adb"),
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        r"C:\Program Files\Android\platform-tools\adb.exe"
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def is_adb_connected():
    """Checks if a mobile device is currently connected to PC via ADB."""
    adb = get_adb_executable()
    if not adb:
        return False
    try:
        res = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=3)
        lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
        # Skip header 'List of devices attached'
        devices = [l for l in lines[1:] if "device" in l and not l.startswith("*")]
        return len(devices) > 0
    except Exception:
        return False

def capture_mobile_screen():
    """
    Captures the mobile display screen.
    Returns: (PIL.Image or None, bytes or None)
    """
    # 1. Running directly on Android (Termux)
    if is_android_device():
        tmp_screen = "/sdcard/jojo_mob_screen.png"
        try:
            subprocess.run(["screencap", "-p", tmp_screen], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            if os.path.exists(tmp_screen) and os.path.getsize(tmp_screen) > 1000:
                with open(tmp_screen, "rb") as f:
                    data = f.read()
                im = Image.open(io.BytesIO(data))
                return im, data
        except Exception as e:
            print(f"⚠️ Android native screencap error: {e}")

    # 2. Running from PC with ADB connected device
    adb = get_adb_executable()
    if adb and is_adb_connected():
        try:
            res = subprocess.run([adb, "exec-out", "screencap", "-p"], capture_output=True, timeout=6)
            if res.returncode == 0 and len(res.stdout) > 1000:
                data = res.stdout
                im = Image.open(io.BytesIO(data))
                return im, data
        except Exception as e:
            print(f"⚠️ ADB screencap error: {e}")

    return None, None

def mobile_tap(x, y):
    """Executes a touch tap on mobile at (x, y)."""
    # On Android directly
    if is_android_device():
        try:
            subprocess.run(["input", "tap", str(int(x)), str(int(y))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    # From PC via ADB
    adb = get_adb_executable()
    if adb and is_adb_connected():
        try:
            subprocess.run([adb, "shell", "input", "tap", str(int(x)), str(int(y))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    return False

def mobile_swipe(x1, y1, x2, y2, duration=300):
    """Executes a swipe gesture on mobile."""
    if is_android_device():
        try:
            subprocess.run(["input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    adb = get_adb_executable()
    if adb and is_adb_connected():
        try:
            subprocess.run([adb, "shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    return False

def mobile_keyevent(key_name_or_code):
    """Presses an Android hardware/system key."""
    key_map = {
        "back": "4",
        "home": "3",
        "enter": "66",
        "power": "26",
        "volume_up": "24",
        "volume_down": "25",
        "menu": "82",
        "tab": "61",
        "space": "62",
        "del": "67",
        "backspace": "67",
        "notifications": "expand_notifications"
    }

    code = key_map.get(str(key_name_or_code).lower(), str(key_name_or_code))

    if is_android_device():
        try:
            if code == "expand_notifications":
                subprocess.run(["cmd", "statusbar", "expand-notifications"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["input", "keyevent", str(code)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    adb = get_adb_executable()
    if adb and is_adb_connected():
        try:
            if code == "expand_notifications":
                subprocess.run([adb, "shell", "cmd", "statusbar", "expand-notifications"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run([adb, "shell", "input", "keyevent", str(code)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    return False

def mobile_type_text(text):
    """Types text into active input on mobile."""
    # Escape characters for adb shell input
    clean_text = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
    if is_android_device():
        try:
            subprocess.run(["input", "text", clean_text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    adb = get_adb_executable()
    if adb and is_adb_connected():
        try:
            subprocess.run([adb, "shell", "input", "text", clean_text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    return False

def ai_locate_mobile_element(target_name, img_bytes=None, width=None, height=None):
    """
    Uses Gemini 3.6 Flash to analyze a mobile screenshot and find exact center coordinates (x, y)
    of the target UI element on mobile screen.
    """
    if not img_bytes:
        im, img_bytes = capture_mobile_screen()
        if not im or not img_bytes:
            return {"found": False, "error": "Could not capture mobile screen"}
        width, height = im.size

    prompt = f"""You are a mobile UI automation expert.
Mobile screen resolution: {width} width by {height} height (portrait orientation).
Locate the element matching: "{target_name}".
This could be a button, permission option ("Allow", "Deny", "While using the app"),
a Bluetooth device name, toggle switch, setting row, or icon on the mobile screen.
Find the exact center coordinates (x, y) to tap this element.
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
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                prompt
            ])
            text = resp.text.strip()
            text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)
            return data
        except Exception as e:
            print(f"⚠️ Gemini Mobile Vision locator error: {e}")
            rotate_gemini_key()
            attempts += 1

    return {"found": False, "error": "AI Vision locator quota/network error"}

def ai_mobile_click_element(target_name):
    """
    Complete Mobile Autonomous Click Flow:
    1. Grabs mobile screen
    2. Runs Gemini Vision Grounding
    3. Taps element on mobile
    Returns: (success: bool, reply_message: str)
    """
    print(f"📱 JoJo Mobile AI Vision scanning screen for: '{target_name}'...")
    im, img_bytes = capture_mobile_screen()
    if not im or not img_bytes:
        return False, "बॉस, मोबाइल स्क्रीन कैप्चर नहीं हो पाई! चेक करें कि मोबाइल अनलॉक है या नहीं।"

    width, height = im.size
    data = ai_locate_mobile_element(target_name, img_bytes, width, height)

    if not data or not data.get("found"):
        return False, f"बॉस, मोबाइल स्क्रीन पर '{target_name}' नहीं दिख रहा है!"

    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    elem = data.get("element_name", target_name)
    conf = data.get("confidence", 1.0)

    print(f"🎯 Mobile AI Vision found '{elem}' at ({x}, {y}) [Confidence: {conf}]")
    tapped = mobile_tap(x, y)

    if tapped:
        return True, f"हाँ बॉस! मोबाइल पर '{elem}' पर टैप कर दिया!"
    else:
        return True, f"बॉस, मोबाइल पर '{elem}' मिला ({x}, {y}) पर, टैप कमांड भेज दिया!"
