from jojo_config import api_keys, make_client, MODEL
"""
🌅 JoJo AGI: JoJo Daily Digest & Morning Briefing Agent
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
- Aggregates multi-source real-time context:
  * Current date, time, and day
  * Live local weather
  * Computer diagnostics (CPU, RAM, Battery)
  * Recent semantic memories and activity episodes
- Synthesizes an executive daily briefing tailored for Boss (the configured owner)
- Generates both a readable briefing and a spoken voice-ready script
"""

import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_tools import get_live_weather
from jojo_agi.jojo_execution_engine import get_system_diagnostics
from jojo_agi.jojo_memory_engine import recall_relevant_episodes, search_semantic_memory

from google import genai
from google.genai import types

GEMINI_KEYS = api_keys()
_digest_key_idx = 0

def get_gemini_client():
    global _digest_key_idx
    key = GEMINI_KEYS[_digest_key_idx]
    return make_client(api_key=key)

def rotate_key():
    global _digest_key_idx
    _digest_key_idx = (_digest_key_idx + 1) % max(1, len(GEMINI_KEYS))


def generate_daily_digest(
    city: str = "auto",
    user_focus: str = "general coding and system productivity"
) -> str:
    """
    Generates a personalized Morning Briefing & Daily Digest for Boss.
    Aggregates weather, PC system diagnostics, recent memories, and today's priorities.
    Args:
        city: City for weather report (default: 'auto').
        user_focus: Main focus area for today.
    """
    now = datetime.now()
    date_str = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%I:%M %p")

    # 1. Fetch live weather
    weather_info = get_live_weather(city)

    # 2. Fetch PC Diagnostics
    pc_diagnostics = get_system_diagnostics()

    # 3. Recall recent memory notes
    recent_memories = search_semantic_memory("boss preferences and ongoing projects", top_k=3)
    memory_summary = "\n".join([f"• [{m.get('category')}] {m.get('content')}" for m in recent_memories]) if recent_memories else "No recent memory flags."

    # 4. Formulate synthesis prompt
    prompt = (
        f"You are JoJo, the configured owner's loyal AGI companion, generating the JoJo Daily Morning Briefing.\n\n"
        f"Context:\n"
        f"- Date: {date_str}, {time_str}\n"
        f"- Boss Name: the configured owner (संस्कार गोखरू)\n"
        f"- Weather:\n{weather_info}\n"
        f"- PC Health:\n{pc_diagnostics}\n"
        f"- Relevant Knowledge & Memory:\n{memory_summary}\n"
        f"- Today's Focus: {user_focus}\n\n"
        f"Generate a crisp, brotherly, motivating Daily Briefing in natural Hinglish with these 4 sections:\n"
        f"1. ☀️ Good Morning Boss & Weather Overview\n"
        f"2. 💻 PC Health & System Readiness\n"
        f"3. 🎯 Priority Focus for Today\n"
        f"4. ⚡ JoJo's Quick Proactive Tip or Joke\n\n"
        f"Keep the tone confident, warm, energetic, and completely grounded in the actual stats provided."
    )

    for _ in range(len(GEMINI_KEYS)):
        try:
            client = get_gemini_client()
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=700)
            )
            digest = resp.text.strip()
            
            # Save digest to scratch
            out_dir = os.path.join(WORKSPACE_ROOT, "scratch", "daily_digests")
            os.makedirs(out_dir, exist_ok=True)
            today_file = os.path.join(out_dir, f"digest_{now.strftime('%Y%m%d')}.md")
            with open(today_file, "w", encoding="utf-8") as f:
                f.write(digest)

            return digest
        except Exception:
            rotate_key()

    return (
        f"🌅 Good Morning Boss!\n"
        f"Date: {date_str} ({time_str})\n\n"
        f"{weather_info}\n\n"
        f"{pc_diagnostics}\n\n"
        f"आज का फोकस: {user_focus}. ऑल सिस्टम्स गो, बॉस!"
    )
