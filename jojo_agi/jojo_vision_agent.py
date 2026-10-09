from jojo_config import api_keys, make_client, MODEL, DATA_DIR
"""
👁️ JoJo AGI: Vision & UI Perception Agent
Enables autonomous visual inspection of the Windows desktop using Gemini Vision:
- Captures current screen state
- Visually inspects errors, active applications, code, browser windows
- Locates and clicks UI elements
- Sends keyboard strokes and text input
"""

import os
import sys
import time
from PIL import Image, ImageGrab
import pyautogui
pyautogui.FAILSAFE = True

try:
    import pyperclip
except ImportError:
    pyperclip = None

from google import genai
from google.genai import types

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

import jojo_vision_click as jvc

GEMINI_KEYS = api_keys()
_key_idx = 0

def get_gemini_client():
    global _key_idx
    return make_client(api_key=GEMINI_KEYS[_key_idx])

def inspect_screen(query: str = "What is currently visible on the screen? Identify active windows, code, or any errors.") -> str:
    """Takes a live screenshot of the desktop and visually analyzes it using Gemini Vision."""
    from jojo_policy import guard_desktop
    guard_desktop(query)
    from jojo_desktop_guard import guard_capture
    guard_capture()
    global _key_idx
    screenshot_path = os.path.join(WORKSPACE_ROOT, "scratch", "current_agent_view.png")
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    try:
        # Capture screenshot
        img = ImageGrab.grab()
        # Scale down slightly if 4K to optimize speed and API payload
        if img.width > 1920:
            ratio = 1920 / img.width
            img = img.resize((1920, int(img.height * ratio)), Image.Resampling.LANCZOS)
        img.save(screenshot_path, "PNG")
    except Exception as e:
        return f"⚠️ Screenshot capture failed: {str(e)}"

    prompt = (
        f"You are the visual sensory system of JoJo, an autonomous AI agent running on a Windows PC.\n"
        f"Analyze this desktop screenshot to answer the following query:\n"
        f"QUERY: {query}\n\n"
        f"Be precise, mention window titles, visible text, status messages, code errors, or UI buttons relevant to the query."
    )

    for _ in range(len(GEMINI_KEYS)):
        try:
            client = get_gemini_client()
            with open(screenshot_path, "rb") as f:
                img_bytes = f.read()

            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=600
                )
            )
            return f"👁️ Visual Screen Observation:\n{response.text.strip()}"
        except Exception as e:
            print(f"⚠️ Gemini Vision key error: {e}")
            _key_idx = (_key_idx + 1) % max(1, len(GEMINI_KEYS))

    return "⚠️ Failed to visually analyze screen with Gemini Vision."

def click_screen_element(element_name: str) -> str:
    """Visually locates a button, icon, or text element on screen and clicks it."""
    ok, msg = jvc.ai_click_element(element_name)
    return msg

def type_text(text: str) -> str:
    """Types text into the active focused window using clipboard paste."""
    from jojo_policy import guard_desktop
    guard_desktop(text)
    from jojo_desktop_guard import guard_focus
    guard_focus()
    try:
        if pyperclip:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            return f"⌨️ Typed text: '{text[:50]}...'"
        else:
            pyautogui.write(text, interval=0.02)
            return f"⌨️ Typed text: '{text[:50]}...'"
    except Exception as e:
        return f"⚠️ Error typing text: {str(e)}"

def press_key(key: str) -> str:
    """Presses a keyboard key or hotkey combination (e.g. 'enter', 'esc', 'ctrl+s', 'alt+f4')."""
    from jojo_policy import guard_desktop
    guard_desktop(key)
    from jojo_desktop_guard import guard_focus
    guard_focus()
    try:
        keys = [k.strip().lower() for k in key.split("+")]
        if len(keys) > 1:
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(keys[0])
        return f"⌨️ Pressed key: {key}"
    except Exception as e:
        return f"⚠️ Error pressing key {key}: {str(e)}"
