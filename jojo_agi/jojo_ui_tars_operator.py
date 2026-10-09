"""
🎯 JoJo AGI: UI-TARS Universal Operator (Desktop & Mobile)
Adapted from ByteDance UI-TARS-desktop (nut-js & adb operators):
- Complete Action Space execution:
  * click(start_box='[x1, y1, x2, y2]')
  * left_double(start_box='[x1, y1, x2, y2]')
  * right_single(start_box='[x1, y1, x2, y2]')
  * middle_click(start_box='[x1, y1, x2, y2]')
  * drag(start_box='[x1, y1, x2, y2]', end_box='[x3, y3, x4, y4]')
  * hotkey(key='ctrl c')
  * type(content='...') with Unicode clipboard paste & newline submission
  * scroll(start_box='[x1, y1, x2, y2]', direction='down|up|left|right')
  * wait()
  * finished(content='...')
  * call_user()
- Desktop Windows Operator with PyAutoGUI & ctypes
- Mobile Android Operator with ADB (input tap, swipe, keyevent, text)
"""

import os
import sys
import time
import subprocess
import shutil
import math
from typing import Dict, Any, Tuple, Optional, List

# Windows specific
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pyautogui
pyautogui.FAILSAFE = True

try:
    import pyperclip
except ImportError:
    pyperclip = None

from PIL import Image, ImageGrab

# Hotkey normalization map
DESKTOP_KEY_MAP = {
    "return": "enter",
    "enter": "enter",
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "win": "win",
    "windows": "win",
    "cmd": "win",
    "command": "win",
    "meta": "win",
    "esc": "esc",
    "escape": "esc",
    "tab": "tab",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "page up": "pageup",
    "page down": "pagedown",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "home": "home",
    "end": "end",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12",
}

ADB_KEY_MAP = {
    "enter": "KEYCODE_ENTER",
    "return": "KEYCODE_ENTER",
    "back": "KEYCODE_BACK",
    "home": "KEYCODE_HOME",
    "backspace": "KEYCODE_DEL",
    "delete": "KEYCODE_FORWARD_DEL",
    "menu": "KEYCODE_MENU",
    "power": "KEYCODE_POWER",
    "volume_up": "KEYCODE_VOLUME_UP",
    "volume_down": "KEYCODE_VOLUME_DOWN",
    "mute": "KEYCODE_MUTE",
    "tab": "KEYCODE_TAB",
    "space": "KEYCODE_SPACE",
    "escape": "KEYCODE_ESCAPE",
    "esc": "KEYCODE_ESCAPE",
    "up": "KEYCODE_DPAD_UP",
    "down": "KEYCODE_DPAD_DOWN",
    "left": "KEYCODE_DPAD_LEFT",
    "right": "KEYCODE_DPAD_RIGHT",
}


class UITarsDesktopOperator:
    """Desktop Operator implementing UI-TARS action specifications on Windows."""

    def __init__(self):
        pyautogui.FAILSAFE = True

    def get_screen_size(self) -> Tuple[int, int]:
        """Returns (width, height) of primary screen."""
        try:
            return pyautogui.size()
        except Exception:
            return 1920, 1080

    def capture_screenshot(self, save_path: Optional[str] = None) -> Image.Image:
        """Captures desktop screen safely."""
        from jojo_policy import guard_desktop
        guard_desktop()
        from jojo_desktop_guard import guard_capture
        guard_capture()
        try:
            img = ImageGrab.grab()
        except Exception:
            img = pyautogui.screenshot()
        
        if save_path:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            img.save(save_path, "PNG")
        return img

    def execute_action(self, action_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a parsed UI-TARS action dictionary.
        Expected keys:
            action_type: str (e.g. 'click', 'left_double', 'type', 'hotkey', 'scroll', etc.)
            action_inputs: dict with start_coords, end_coords, content, key, direction, etc.
        """
        action_type = action_dict.get("action_type", "").lower()
        from jojo_policy import guard_desktop
        guard_desktop(str(action_dict))
        inputs = action_dict.get("action_inputs", {})
        
        screen_w, screen_h = self.get_screen_size()
        start_coords = inputs.get("start_coords")
        end_coords = inputs.get("end_coords")
        from jojo_desktop_guard import guard_point, guard_focus
        if action_type in {'click','left_click','left_single','left_double','double_click','right_single','right_click','middle_click','drag','left_click_drag','select'}:
            point = start_coords or pyautogui.position()
            guard_point(*point[:2])
            if end_coords:guard_point(*end_coords[:2])
        elif action_type in {'type','hotkey','press','key'}:
            guard_focus()

        result = {
            "status": "success",
            "action_type": action_type,
            "message": "",
            "details": {}
        }

        try:
            if action_type in ["click", "left_click", "left_single"]:
                if start_coords and len(start_coords) >= 2:
                    x, y = int(start_coords[0]), int(start_coords[1])
                    pyautogui.moveTo(x, y, duration=0.15)
                    time.sleep(0.05)
                    pyautogui.click(x, y)
                    result["message"] = f"Clicked at ({x}, {y})"
                    result["details"]["coords"] = (x, y)
                else:
                    pyautogui.click()
                    result["message"] = "Clicked at current position"

            elif action_type in ["left_double", "double_click"]:
                if start_coords and len(start_coords) >= 2:
                    x, y = int(start_coords[0]), int(start_coords[1])
                    pyautogui.moveTo(x, y, duration=0.15)
                    time.sleep(0.05)
                    pyautogui.doubleClick(x, y)
                    result["message"] = f"Double-clicked at ({x}, {y})"
                    result["details"]["coords"] = (x, y)
                else:
                    pyautogui.doubleClick()
                    result["message"] = "Double-clicked at current position"

            elif action_type in ["right_single", "right_click"]:
                if start_coords and len(start_coords) >= 2:
                    x, y = int(start_coords[0]), int(start_coords[1])
                    pyautogui.moveTo(x, y, duration=0.15)
                    time.sleep(0.05)
                    pyautogui.rightClick(x, y)
                    result["message"] = f"Right-clicked at ({x}, {y})"
                    result["details"]["coords"] = (x, y)
                else:
                    pyautogui.rightClick()
                    result["message"] = "Right-clicked at current position"

            elif action_type in ["middle_click"]:
                if start_coords and len(start_coords) >= 2:
                    x, y = int(start_coords[0]), int(start_coords[1])
                    pyautogui.moveTo(x, y, duration=0.15)
                    pyautogui.middleClick(x, y)
                    result["message"] = f"Middle-clicked at ({x}, {y})"
                else:
                    pyautogui.middleClick()
                    result["message"] = "Middle-clicked at current position"

            elif action_type in ["mouse_move", "hover"]:
                if start_coords and len(start_coords) >= 2:
                    x, y = int(start_coords[0]), int(start_coords[1])
                    pyautogui.moveTo(x, y, duration=0.2)
                    result["message"] = f"Moved mouse to ({x}, {y})"

            elif action_type in ["drag", "left_click_drag", "select"]:
                if start_coords and len(start_coords) >= 2 and end_coords and len(end_coords) >= 2:
                    sx, sy = int(start_coords[0]), int(start_coords[1])
                    ex, ey = int(end_coords[0]), int(end_coords[1])
                    pyautogui.moveTo(sx, sy, duration=0.15)
                    time.sleep(0.05)
                    pyautogui.dragTo(ex, ey, duration=0.4, button='left')
                    result["message"] = f"Dragged from ({sx}, {sy}) to ({ex}, {ey})"
                    result["details"]["drag"] = {"start": (sx, sy), "end": (ex, ey)}
                else:
                    result["status"] = "error"
                    result["message"] = "Drag requires both start_coords and end_coords"

            elif action_type == "type":
                content = inputs.get("content", "")
                should_press_enter = content.endswith("\n") or content.endswith("\\n")
                clean_content = content.rstrip("\r\n").replace("\\n", "")

                # High reliability Unicode typing via clipboard paste (UI-TARS pattern)
                if clean_content:
                    old_clipboard = ""
                    try:
                        if pyperclip:
                            old_clipboard = pyperclip.paste()
                            pyperclip.copy(clean_content)
                            time.sleep(0.03)
                            pyautogui.hotkey('ctrl', 'v')
                            time.sleep(0.05)
                            # Restore clipboard
                            if old_clipboard:
                                pyperclip.copy(old_clipboard)
                        else:
                            pyautogui.write(clean_content, interval=0.01)
                    except Exception as e:
                        pyautogui.write(clean_content, interval=0.01)

                if should_press_enter:
                    time.sleep(0.05)
                    guard_focus()
                    pyautogui.press('enter')

                result["message"] = f"Typed content: '{clean_content}' (enter={should_press_enter})"
                result["details"]["content"] = clean_content

            elif action_type == "hotkey":
                key_str = inputs.get("key") or inputs.get("hotkey") or ""
                # Keys can be space-separated or plus-separated (e.g. 'ctrl c' or 'ctrl+c')
                raw_keys = [k.strip().lower() for k in key_str.replace("+", " ").split()]
                normalized = [DESKTOP_KEY_MAP.get(k, k) for k in raw_keys if k]
                
                if normalized:
                    pyautogui.hotkey(*normalized)
                    result["message"] = f"Pressed hotkey: {'+'.join(normalized)}"
                    result["details"]["keys"] = normalized
                else:
                    result["status"] = "error"
                    result["message"] = f"Empty or invalid hotkey '{key_str}'"

            elif action_type == "press":
                key_str = inputs.get("key", "").lower().strip()
                k = DESKTOP_KEY_MAP.get(key_str, key_str)
                pyautogui.keyDown(k)
                result["message"] = f"Key down: {k}"

            elif action_type == "release":
                key_str = inputs.get("key", "").lower().strip()
                k = DESKTOP_KEY_MAP.get(key_str, key_str)
                pyautogui.keyUp(k)
                result["message"] = f"Key up: {k}"

            elif action_type == "scroll":
                if start_coords and len(start_coords) >= 2:
                    sx, sy = int(start_coords[0]), int(start_coords[1])
                    pyautogui.moveTo(sx, sy, duration=0.1)

                direction = str(inputs.get("direction", "down")).lower()
                amount = int(inputs.get("amount", 5)) # UI-TARS uses 5 clicks default

                if direction == "up":
                    pyautogui.scroll(amount * 120)
                    result["message"] = f"Scrolled up by {amount} clicks"
                elif direction == "down":
                    pyautogui.scroll(-amount * 120)
                    result["message"] = f"Scrolled down by {amount} clicks"
                elif direction in ["left", "right"]:
                    # Horizontal scroll via shift + mousewheel or horizontal API
                    h_amount = (amount * 120) if direction == "right" else (-amount * 120)
                    try:
                        pyautogui.hscroll(h_amount)
                    except AttributeError:
                        pyautogui.keyDown('shift')
                        pyautogui.scroll(amount * 120 if direction == "right" else -amount * 120)
                        pyautogui.keyUp('shift')
                    result["message"] = f"Scrolled {direction}"

            elif action_type == "wait":
                duration = float(inputs.get("duration", 2.0))
                time.sleep(duration)
                result["message"] = f"Waited for {duration} seconds"

            elif action_type in ["finished", "call_user", "error_env", "user_stop"]:
                content = inputs.get("content", "")
                result["status"] = "completed" if action_type == "finished" else "need_assistance"
                result["message"] = f"Task termination via {action_type}: {content}"
                result["details"]["content"] = content

            else:
                result["status"] = "warning"
                result["message"] = f"Unknown action type: '{action_type}'"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"Failed executing action {action_type}: {str(e)}"

        return result


class UITarsMobileOperator:
    """Mobile Operator implementing UI-TARS action specifications via ADB."""

    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id or self._auto_detect_device()
        self.adb_bin = self._find_adb()

    def _find_adb(self) -> str:
        candidates = [
            shutil.which("adb"),
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            r"C:\Program Files\Android\platform-tools\adb.exe"
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return "adb"

    def _auto_detect_device(self) -> Optional[str]:
        adb = shutil.which("adb") or "adb"
        try:
            res = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=3)
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            devices = [l.split("\t")[0].strip() for l in lines[1:] if "device" in l and not l.startswith("*")]
            return devices[0] if devices else None
        except Exception:
            return None

    def is_available(self) -> bool:
        return bool(self.device_id)

    def _run_adb(self, cmd_args: List[str], timeout: int = 5) -> str:
        prefix = [self.adb_bin]
        if self.device_id:
            prefix.extend(["-s", self.device_id])
        full_cmd = prefix + cmd_args
        res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode:
            raise RuntimeError('ADB failed: ' + res.stderr[:300])
        return res.stdout.strip()

    def guard_mobile(self, value=''):
        from jojo_policy import require_allowed
        require_allowed(value)
        window = self._run_adb(['shell', 'dumpsys', 'window', 'windows'])
        foreground = next((line for line in window.splitlines() if 'mCurrentFocus=' in line and 'null' not in line), '')
        if not foreground:
            raise PermissionError('Cannot verify the foreground Android app; action refused.')
        require_allowed(foreground)

    def capture_screenshot(self, save_path: Optional[str] = None) -> Optional[Image.Image]:
        """Captures mobile screen using ADB screencap."""
        self.guard_mobile()
        prefix = [self.adb_bin]
        if self.device_id:
            prefix.extend(["-s", self.device_id])
        cmd = prefix + ["exec-out", "screencap", "-p"]
        try:
            import io
            res = subprocess.run(cmd, capture_output=True, timeout=8)
            if res.stdout:
                img = Image.open(io.BytesIO(res.stdout))
                if save_path:
                    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                    img.save(save_path, "PNG")
                return img
        except Exception as e:
            print(f"⚠️ ADB screencap failed: {e}")
        return None

    def execute_action(self, action_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a parsed UI-TARS action dictionary on the Android device."""
        self.guard_mobile(str(action_dict))
        action_type = action_dict.get("action_type", "").lower()
        inputs = action_dict.get("action_inputs", {})
        start_coords = inputs.get("start_coords")
        end_coords = inputs.get("end_coords")

        result = {
            "status": "success",
            "action_type": action_type,
            "message": "",
            "details": {}
        }

        try:
            if action_type in ["click", "left_click", "left_single"]:
                if start_coords and len(start_coords) >= 2:
                    x, y = int(round(start_coords[0])), int(round(start_coords[1]))
                    self._run_adb(["shell", "input", "tap", str(x), str(y)])
                    result["message"] = f"ADB tapped ({x}, {y})"
                else:
                    result["status"] = "error"
                    result["message"] = "Click missing coordinates"

            elif action_type in ["swipe", "drag"]:
                if start_coords and len(start_coords) >= 2 and end_coords and len(end_coords) >= 2:
                    sx, sy = int(round(start_coords[0])), int(round(start_coords[1]))
                    ex, ey = int(round(end_coords[0])), int(round(end_coords[1]))
                    duration = int(inputs.get("duration", 300))
                    self._run_adb(["shell", "input", "swipe", str(sx), str(sy), str(ex), str(ey), str(duration)])
                    result["message"] = f"ADB swiped ({sx}, {sy}) -> ({ex}, {ey})"
                else:
                    result["status"] = "error"
                    result["message"] = "Swipe requires start and end coordinates"

            elif action_type == "scroll":
                direction = str(inputs.get("direction", "down")).lower()
                # Default screen center swipe if start_coords missing
                sx = int(round(start_coords[0])) if start_coords else 500
                sy = int(round(start_coords[1])) if start_coords else 1000

                # Scroll down means content goes up (drag finger up)
                if direction == "down":
                    self._run_adb(["shell", "input", "swipe", str(sx), str(sy), str(sx), str(max(100, sy - 600)), "350"])
                elif direction == "up":
                    self._run_adb(["shell", "input", "swipe", str(sx), str(sy), str(sx), str(sy + 600), "350"])
                elif direction == "right":
                    self._run_adb(["shell", "input", "swipe", str(sx), str(sy), str(max(100, sx - 400)), str(sy), "300"])
                elif direction == "left":
                    self._run_adb(["shell", "input", "swipe", str(sx), str(sy), str(sx + 400), str(sy), "300"])
                result["message"] = f"ADB scrolled {direction}"

            elif action_type == "type":
                content = inputs.get("content", "")
                clean = content.rstrip("\r\n").replace("\\n", "")
                # Shell input text
                escaped = clean.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
                self._run_adb(["shell", "input", "text", escaped])
                if content.endswith("\n") or content.endswith("\\n"):
                    self._run_adb(["shell", "input", "keyevent", "KEYCODE_ENTER"])
                result["message"] = f"ADB typed text: '{clean}'"

            elif action_type == "hotkey":
                key = str(inputs.get("key", "")).lower().strip()
                adb_key = ADB_KEY_MAP.get(key, f"KEYCODE_{key.upper()}")
                self._run_adb(["shell", "input", "keyevent", adb_key])
                result["message"] = f"ADB keyevent: {adb_key}"

            elif action_type == "press_home":
                self._run_adb(["shell", "input", "keyevent", "KEYCODE_HOME"])
                result["message"] = "ADB pressed HOME"

            elif action_type == "wait":
                time.sleep(2.0)
                result["message"] = "ADB waited 2s"

            elif action_type in ["finished", "call_user"]:
                result["status"] = "completed" if action_type == "finished" else "need_assistance"
                result["message"] = f"Mobile task finished: {inputs.get('content', '')}"

            else:
                result["status"] = "warning"
                result["message"] = f"Unsupported mobile action: {action_type}"

        except Exception as e:
            result["status"] = "error"
            result["message"] = f"ADB error on {action_type}: {str(e)}"

        return result


class UITarsUnifiedOperator:
    """Unified Operator that switches seamlessly between Desktop and Mobile ADB."""

    def __init__(self, prefer_target: str = "desktop"):
        self.desktop = UITarsDesktopOperator()
        self.mobile = UITarsMobileOperator()
        self.target = prefer_target.lower()

    def set_target(self, target: str):
        self.target = target.lower()

    def get_current_target(self) -> str:
        if self.target == "mobile":
            if not self.mobile.is_available():
                raise RuntimeError('No authorized Android device connected. No laptop action was substituted.')
            return "mobile"
        return "desktop"

    def capture_screenshot(self, save_path: Optional[str] = None) -> Image.Image:
        if self.get_current_target() == "mobile":
            img = self.mobile.capture_screenshot(save_path)
            if img:
                return img
            raise RuntimeError('Android screenshot failed. No laptop screenshot was substituted.')
        return self.desktop.capture_screenshot(save_path)

    def execute_action(self, action_dict: Dict[str, Any]) -> Dict[str, Any]:
        if self.get_current_target() == "mobile":
            return self.mobile.execute_action(action_dict)
        return self.desktop.execute_action(action_dict)
