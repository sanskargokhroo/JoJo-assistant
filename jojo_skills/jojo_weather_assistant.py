"""
📦 JoJo Skill: Weather Assistant
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
"""
import os
import sys
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_tools import get_live_weather

def check_weather(city: str = "auto") -> str:
    """Checks live weather and forecast for any city or location without an API key.
    Args:
        city: City name (e.g. 'Mumbai', 'Delhi', 'New York') or 'auto'.
    """
    return get_live_weather(city)
