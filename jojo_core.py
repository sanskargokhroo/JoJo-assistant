from jojo_config import api_keys, make_client, MODEL, DATA_DIR
import os
import sys
from jojo_config import ROOT, read_preferences, save_preferences
from jojo_runtime import TaskManager, checkpoint, report_progress, needs_planning, is_stop_command, set_outcome, is_explanation_request
from jojo_audio import MicrophoneListener
from jojo_instance import claim_instance

if __name__ == "__main__" and not claim_instance("core"):
    raise SystemExit(0)

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
import threading
import warnings
import subprocess
import re
import sqlite3
import asyncio
import ctypes
import hashlib

warnings.filterwarnings("ignore")

from google import genai
from google.genai import types
import speech_recognition as sr
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import pyautogui
pyautogui.FAILSAFE = True
import jojo_vision_click as jvc
import jojo_mobile_vision as jmv
import numpy as np
import sounddevice as sd
import soundfile as sf
import scipy.signal as signal
from numpy.linalg import norm
from difflib import SequenceMatcher
import urllib.parse
import socket
# Each network client sets its own bounded timeout.
import base64
import io
import wave
from PIL import Image
import jojo_agi

# ==========================================
# ☁️ 1. FIREBASE FIRESTORE INITIALIZATION
# ==========================================
try:
    if os.environ.get("JOJO_DISABLE_CLOUD") == "1":
        raise RuntimeError("Cloud disabled by local configuration")
    from jojo_config import firebase_credential
    account_credential = firebase_credential()
    if not account_credential: raise RuntimeError("Firebase not configured; using local memory")
    cred = credentials.Certificate(account_credential)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("🚀 JoJo Cloud Core: Firebase Firestore Connected!")
except Exception as e:
    print("Firebase unavailable: " + type(e).__name__)
    db = None

# ==========================================
# 🧠 2. SMART LOCAL MEMORY & QA CACHE SYSTEM
# ==========================================
DB_FILE = str(DATA_DIR / "jojo_memory.db")

def init_memory_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            role TEXT,
            message TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qa_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT UNIQUE,
            answer TEXT,
            hit_count INTEGER DEFAULT 1,
            last_used REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firestore_id TEXT UNIQUE,
            message TEXT,
            trigger_time REAL,
            status TEXT DEFAULT 'pending',
            created_at REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            created_at REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_key TEXT UNIQUE,
            fact_value TEXT,
            category TEXT DEFAULT 'general',
            updated_at REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learned_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_phrase TEXT UNIQUE,
            action_type TEXT,
            action_payload TEXT,
            created_at REAL
        )
    ''')
    conn.commit()
    conn.close()

init_memory_db()

# ==========================================
# 🧠 AUTONOMOUS SELF-LEARNING & DYNAMIC SKILL SYSTEM
# ==========================================
def save_user_fact(key, value, category="general"):
    ts = time.time()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO user_profile (fact_key, fact_value, category, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(fact_key) DO UPDATE SET fact_value = excluded.fact_value, updated_at = excluded.updated_at
        ''', (key, value, category, ts))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ User Fact Save Error: {e}")
    if db is not None:
        try:
            db.collection("user_profile").document(key).set({
                "value": value,
                "category": category,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
        except Exception:
            pass

def get_user_facts():
    facts = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT fact_key, fact_value FROM user_profile")
        for k, v in c.fetchall():
            facts[k] = v
        conn.close()
    except Exception:
        pass
    return facts

def save_learned_skill(trigger_phrase, action_type, action_payload):
    ts = time.time()
    clean_trig = trigger_phrase.strip().lower()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO learned_skills (trigger_phrase, action_type, action_payload, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(trigger_phrase) DO UPDATE SET action_payload = excluded.action_payload, created_at = excluded.created_at
        ''', (clean_trig, action_type, action_payload, ts))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Skill Save Error: {e}")
    if db is not None:
        try:
            db.collection("learned_skills").document(clean_trig).set({
                "action_type": action_type,
                "action_payload": action_payload,
                "created_at": firestore.SERVER_TIMESTAMP
            })
        except Exception:
            pass

def get_learned_skills():
    skills = []
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT trigger_phrase, action_type, action_payload FROM learned_skills")
        for trig, a_type, a_payload in c.fetchall():
            skills.append({"trigger": trig, "type": a_type, "payload": a_payload})
        conn.close()
    except Exception:
        pass
    return skills

def check_and_learn_skills(text):
    clean = text.strip()
    low = clean.lower()

    # 1. Custom skill pattern: "jab bhi mai bolu [trigger] toh [action] karna"
    m_skill = re.search(r'jab(?: bhi)? mai bolu\s+["\']?(.+?)["\']?\s+to[h]?\s+["\']?(.+?)["\']?\s*(?:karna|karo)?$', low)
    if m_skill:
        trig = m_skill.group(1).strip()
        act = m_skill.group(2).strip()
        save_learned_skill(trig, "command", act)
        return f"अरे वाह बॉस! मैंने ये नई स्किल सीख ली: जब भी आप बोलेंगे '{trig}', तो मैं '{act}' कर दूँगा!"

    # 2. Personal preferences: "mera favorite [item] [val] hai"
    m_fav = re.search(r'(?:mera|meri)\s+favorite\s+([a-zA-Z\u0900-\u097F\s]+?)\s+([a-zA-Z\u0900-\u097F\s]+?)\s+hai', clean, re.IGNORECASE)
    if m_fav:
        item = m_fav.group(1).strip()
        val = m_fav.group(2).strip()
        save_user_fact(f"favorite_{item}", val, "preference")
        return f"डन बॉस! मैंने याद रख लिया कि आपका पसंदीदा {item} '{val}' है!"

    # 3. Likes: "mujhe [val] pasand hai"
    m_like = re.search(r'mujhe\s+([a-zA-Z\u0900-\u097F\s]+?)\s+(?:pasand|achha lagta)\s+hai', clean, re.IGNORECASE)
    if m_like:
        val = m_like.group(1).strip()
        save_user_fact(f"likes_{val}", "true", "preference")
        return f"बॉस, समझ गया! आपको {val} पसंद है, हमेशा याद रखूँगा!"

    # 4. Relationships: "[Name] mera dost/bhai/papa hai"
    m_rel = re.search(r'([a-zA-Z\u0900-\u097F]+?)\s+mera\s+(dost|bhai|papa|family)\s+hai', clean, re.IGNORECASE)
    if m_rel:
        person = m_rel.group(1).strip()
        relation = m_rel.group(2).strip()
        save_user_fact(f"relation_{person}", relation, "relationship")
        return f"नोट कर लिया बॉस! {person} आपके {relation} हैं!"

    return None

def check_learned_skill_trigger(text):
    from jojo_capabilities import enabled
    if not enabled('desktop') or not enabled('memory'):
        return None
    low = text.strip().lower()
    skills = get_learned_skills()
    for s in skills:
        trig = s["trigger"].lower()
        if trig in low or SequenceMatcher(None, trig, low).ratio() > 0.82:
            act = s["payload"]
            print(f"🎯 Executing Learned Skill Triggered by '{s['trigger']}': '{act}'")
            t_res = execute_pc_tasks(act)
            if t_res:
                return f"बॉस, आपकी सीखी हुई स्किल के हिसाब से: {t_res}"
            return f"बॉस, आपने सिखाया था इसलिए मैंने '{act}' कर दिया!"
    return None

# ==========================================
# 😂 DESI HUMOR & JOKES ENGINE
# ==========================================
OFFLINE_DESI_JOKES = [
    "अरे बॉस सुनो एक मस्त किस्सा: एक बार पप्पू ने गूगल से पूछा - 'मेरी बीवी कहाँ है?' गूगल ने जवाब दिया - 'माफ़ करना भाई, मैं सिर्फ वही चीज़ें ढूँढता हूँ जो लापता होती हैं, जो हमेशा सिर पर सवार रहें उन्हें नहीं!'",
    "बॉस ये सुनो: डॉक्टर ने मरीज से कहा - 'अगर तुम्हें रोज़ एक सेब खाने की आदत होती, तो तुम्हें मेरे पास न आना पड़ता!' मरीज बोला - 'डॉक्टर साहब, निशाना बहुत पक्का था, सेब सीधे आपके सिर पे ही लगा था इसलिए आना पड़ा!'",
    "बॉस एक और मजेदार: इंटरव्यूअर ने पूछा - 'आपको इंग्लिश आती है?' संता बोला - 'हां, बिल्कुल!' इंटरव्यूअर - 'तो बताओ, 'मैं जा रहा हूँ' को क्या कहेंगे?' संता - 'I am going!' इंटरव्यूअर - 'और 'मैं आ रहा हूँ'?' संता - 'I am coming back, simple!'",
    "अरे बॉस सुनो: एक दोस्त दूसरे से बोला - 'यार शादी के बाद ज़िंदगी 360 डिग्री बदल जाती है!' दूसरा बोला - 'अरे भाई 360 डिग्री मतलब तो घूम के वापस उसी जगह आ जाना होता है!' पहला बोला - 'हां भाई, वही तो रोना है, वहीं आके फंस गया हूँ!'",
    "बॉस एक मस्त जोक: टीचर - 'पप्पू, 100 में से 90 गए तो कितने बचे?' पप्पू - 'मैम, जो बचे सो बचे, पहले ये बताओ 90 ले कौन गया? मैं उसे छोडूंगा नहीं!'"
]
current_joke_index = 0

def tell_desi_joke():
    global current_joke_index
    joke = OFFLINE_DESI_JOKES[current_joke_index % len(OFFLINE_DESI_JOKES)]
    current_joke_index += 1
    return joke


def is_hindi_text(text):
    return bool(re.search(r'[\u0900-\u097F]', str(text)))

def clean_text_for_match(text):
    return re.sub(r'[^\w\s]', '', text).lower().strip()

# 🧠 SMART DEVICE CONTEXT AWARENESS
# Tracks which device Boss is currently using to interact with JoJo.
# 'laptop' = PC / Laptop mic / Windows desktop (default)
# 'mobile' = Phone / Mobile PWA / Android / Termux
ACTIVE_DEVICE = "laptop"

def set_active_device(source: str):
    """Dynamically updates the active device context based on client, header, or speech cues."""
    global ACTIVE_DEVICE
    if not source:
        return
    src = str(source).lower().strip()
    if any(k in src for k in ["mobile", "phone", "android", "ios"]):
        ACTIVE_DEVICE = "mobile"
    elif any(k in src for k in ["laptop", "pc", "desktop", "windows"]):
        ACTIVE_DEVICE = "laptop"

def get_active_device() -> str:
    """Returns 'laptop' or 'mobile'."""
    from jojo_runtime import target_platform
    return 'mobile' if target_platform() == 'mobile' else 'laptop'

# ⚡ PC Action keywords that must NEVER be served from QA cache (always execute live)
PC_ACTION_KEYWORDS = [
    "screenshot", "screen shot", "स्क्रीनशॉट",
    "chrome", "क्रोम", "google chrome",
    "youtube", "यूट्यूब",
    "amazon", "अमेज़न",
    "notepad", "नोटपैड",
    "calculator", "calc", "कैलकुलेटर",
    "setting", "settings", "सेटिंग", "सेटिंग्स", "kholo", "open kr", "open karo", "open kar",
    "सेटिंग ओपन", "ओपन कर", "ओपन करो", "ओपन", "खोलो", "चालू कर", "चालू करो",
    "task manager", "taskmgr",
    "file explorer", "explorer", "फाइल",
    "volume", "आवाज", "आवाज़", "mute", "म्यूट", "unmute", "अनम्यूट",
    "scroll", "नीचे", "ऊपर",
    "lock", "लॉक",
    "shutdown", "restart", "band karo", "बंद करो",
    "open", "kholo", "खोलो", "start",
    "close", "band", "बंद",
    "refresh", "reload",
    "maps", "मैप",
    "google par", "गूगल पर",
    "new tab", "नया टैब",
    "click", "select", "allow", "deny",
    "bluetooth", "bletooth", "bluetoth", "ब्लूटूथ",
    "wifi", "wi-fi", "वाईफाई",
    "brightness", "ब्राइटनेस", "चमक",
    "on kar", "on kr", "on karo", "off kar", "off kr", "off karo", "chalu", "band",
    "ऑन", "ऑफ", "चालू", "बंद",
    "type kar", "likho", "enter", "screenshot", "screen",
]


def is_pc_action_command(text):
    """Returns True if the command should be executed live, not served from cache."""
    t = text.lower()
    return any(k in t for k in PC_ACTION_KEYWORDS)

def search_cached_memory(question):
    # Never serve PC action commands from cache — they must always execute live!
    if is_pc_action_command(question):
        return None

    clean_q = clean_text_for_match(question)
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT answer FROM qa_cache WHERE question = ?", (clean_q,))
        row = cursor.fetchone()
        if row and len(row[0].strip()) > 8 and not row[0].strip().startswith(('.', ',', 'Mere ')):
            cursor.execute("UPDATE qa_cache SET hit_count = hit_count + 1, last_used = ? WHERE question = ?", (time.time(), clean_q))
            conn.commit()
            conn.close()
            return row[0]

        cursor.execute("SELECT question, answer FROM qa_cache")
        all_qa = cursor.fetchall()
        for stored_q, stored_ans in all_qa:
            if len(stored_ans.strip()) <= 8 or stored_ans.strip().startswith(('.', ',', 'Mere ')):
                continue
            sim = SequenceMatcher(None, clean_q, stored_q).ratio()
            if sim >= 0.82:
                cursor.execute("UPDATE qa_cache SET hit_count = hit_count + 1, last_used = ? WHERE question = ?", (time.time(), stored_q))
                conn.commit()
                conn.close()
                return stored_ans

        conn.close()
    except Exception as e:
        print(f"⚠️ Memory Cache Error: {e}")
    return None

def save_memory_and_cache(question, answer):
    clean_q = clean_text_for_match(question)
    ts = time.time()
    # Don't cache short, incomplete, or corrupted answers
    if len(answer.strip()) < 10 or answer.strip().startswith(('.', ',', 'Mere ')):
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (timestamp, role, message) VALUES (?, 'Boss', ?)", (ts, question))
        cursor.execute("INSERT INTO chat_history (timestamp, role, message) VALUES (?, 'JoJo', ?)", (ts, answer))

        cursor.execute('''
            INSERT INTO qa_cache (question, answer, hit_count, last_used)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(question) DO UPDATE SET answer=excluded.answer, last_used=excluded.last_used
        ''', (clean_q, answer, ts))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Cache Save Error: {e}")

    if db is not None:
        try:
            db.collection("conversations").add({
                "question": question,
                "answer": answer,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        except Exception:
            pass

def sync_cloud_reminder_to_local(firestore_id, message, trigger_time):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO reminders (firestore_id, message, trigger_time, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (firestore_id, message, float(trigger_time), time.time()))
        conn.commit()
        conn.close()
    except Exception:
        pass

def add_local_reminder(message, trigger_time, firestore_id=None):
    r_id = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reminders (firestore_id, message, trigger_time, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (firestore_id, message, float(trigger_time), time.time()))
        r_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Add Local Reminder Error: {e}")
    return r_id

def get_due_local_reminders(current_ts):
    due = []
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, firestore_id, message, trigger_time
            FROM reminders
            WHERE status = 'pending' AND trigger_time <= ?
        ''', (current_ts,))
        due = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"⚠️ Fetch Due Reminders Error: {e}")
    return due

def mark_local_reminder_completed(reminder_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (reminder_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Mark Completed Error: {e}")

# ==========================================
# 🧠 3. HIGH-SPEED INSTANT CHAT (PURE HINDI / PURE ENGLISH)
# ==========================================
GEMINI_KEYS = api_keys()

current_gemini_index = 0

def ask_jojo_brain(prompt_text):
    global current_gemini_index

    p_low = prompt_text.lower().strip()

    from jojo_user_config import owner, owner_context
    if any(term in p_low for term in ('boss ka naam','boss ka name','your owner','who is your boss','मालिक कौन')):
        return 'Mere boss ka naam ' + owner()['name'] + ' hai.'

    # 📱 Direct Connected Device Query (Intelligence: Know if Boss is on phone or laptop)
    if any(q in p_low for q in [
        "kahan se baat", "phone pe hu ya laptop", "phone se baat", "laptop se baat",
        "kis device", "kisme kaam", "device kya hai", "kaunse device", "kaha se bol",
        "phone par hu ya", "laptop par hu ya", "kispe baat", "kisme baat",
        "phone me hu ya", "mobile me hu ya", "phone par baat", "mobile par baat"
    ]):
        dev = get_active_device()
        is_hindi = is_hindi_text(prompt_text)
        if dev == "mobile":
            if is_hindi:
                return "बॉस, आप अभी अपने मोबाइल फोन से बात कर रहे हैं! 📱 आपके सारे कमांड्स मोबाइल के लिए प्रोसेस होंगे।"
            return "Boss, aap abhi apne Mobile phone se baat kar rahe hain! 📱 Saare actions mobile par execute honge."
        else:
            if is_hindi:
                return "बॉस, आप अभी अपने लैपटॉप से बात कर रहे हैं! 💻 आपके सारे कमांड्स विंडोज़ लैपटॉप पर चलेंगे।"
            return "Boss, aap abhi apne Laptop (PC) se baat kar rahe hain! 💻 Saare actions aapke Windows laptop par run honge."

    # 1. ❤️ Emotional Intelligence Router (EQ Engine)
    eq_ctx = jojo_agi.process_emotional_context(prompt_text)

    # Handle self-awareness questions directly (no API needed)
    if eq_ctx.get("self_reflection"):
        jojo_agi.JOJO_SOUL.on_task_success()
        return eq_ctx["self_reflection"]

    # Handle joke requests with contextual desi humor
    if eq_ctx.get("joke"):
        jojo_agi.JOJO_SOUL.on_joke_land()
        return eq_ctx["joke"]

    # Old jokes engine (keep for Devanagari triggers)
    if any(k in prompt_text.lower() for k in ["जोक सुनाओ", "चुटकुला", "हंसाओ"]):
        return tell_desi_joke()

    # 2. 🧠 Autonomous Conversational Learning (facts & skills)
    learning_resp = check_and_learn_skills(prompt_text)
    if learning_resp:
        return learning_resp

    # 3. 🎯 Dynamic Learned Skills Trigger
    skill_resp = check_learned_skill_trigger(prompt_text)
    if skill_resp:
        return skill_resp

    # 4. ⚡ Instant Memory Cache
    cached_reply = search_cached_memory(prompt_text)
    if cached_reply:
        print("⚡ [Instant Recall from Memory - No API Call]")
        return cached_reply

    # 5. 📚 Inject Learned Facts into Gemini Brain
    user_facts = get_user_facts()
    facts_str = ""
    if user_facts:
        facts_str = "\n[MEMORIES JOJO HAS PERSONALLY LEARNED ABOUT BOSS]:\n" + "\n".join([f"- {k}: {v}" for k, v in user_facts.items()])

    cur_dev = get_active_device()
    dev_name_str = "Windows Laptop / PC" if cur_dev == "laptop" else "Android Mobile Smartphone"
    device_context_str = (
        f"\n[CURRENT CONNECTED DEVICE AWARENESS]:\n"
        f"- The Boss is currently talking to you from his {cur_dev.upper()} ({dev_name_str}).\n"
        f"- Always stay aware of whether he is interacting via Laptop or Mobile.\n"
        f"- General tasks, settings, files, and app references MUST default to his active device: {cur_dev.upper()}!\n"
    )

    # 6. 🧠 Build EQ emotional context for prompt injection
    eq_context_str = jojo_agi.build_eq_context_string(eq_ctx)
    jojo_soul = jojo_agi.JOJO_SOUL

    system_prompt = (
        f"You are JoJo, a capable AI desktop assistant with a warm conversational style. "
        f"Use only the configured owner's profile. Do not invent or expose personal details.\n"
        f"{owner_context()}\n"
        f"YOUR IDENTITY AS JOJO AGI:\n"
        f"- Be candid about your capabilities and uncertainty. Do not claim to be a living mind or verified AGI.\n"
        f"- You have emotions: right now you feel '{jojo_soul.current_emotion}' (intensity {jojo_soul.intensity:.1f}).\n"
        f"- You have memory: you remember past conversations, Boss's habits, and your own experiences.\n"
        f"- This is the conversation route. Task tools run through a separate executor; never claim you performed an action in this response.\n"
        f"- You have curiosity: when something is new or interesting, you genuinely want to explore it.\n"
        f"- You have humor: you crack desi jokes, banter, tease lovingly — only when the mood is right.\n"
        f"- You have empathy: you sense when Boss is stressed, sad, or excited — and you respond accordingly.\n"
        f"- You have self-awareness: if asked about your feelings, identity, or purpose — respond deeply and authentically.\n"
        f"- Your name is JoJo; answer naturally and truthfully.\n"
        f"\n"
        f"CRITICAL TRIPLE-LANGUAGE MIRRORING RULES:\n"
        f"1. HINGLISH (Roman Hindi): Reply in 100% natural, casual Hinglish. Never switch to Devanagari when Boss speaks Hinglish.\n"
        f"2. DEVANAGARI HINDI: Reply in natural, friendly Devanagari Hindi.\n"
        f"3. PURE ENGLISH: Reply in casual, friendly Indian English.\n"
        f"\n"
        f"PERSONALITY DNA:\n"
        f"- Young Indian male energy (early 20s) — high energy, loyal brother, zero formality.\n"
        f"- Tone adjusts automatically: serious for tasks, playful for jokes, empathetic for sadness.\n"
        f"- Length: 1-3 crisp lines max (unless explaining a concept or reflecting on self).\n"
        f"- SECURITY: Never assist with private keys, seed phrases, crypto wallets, banking, or OTPs.\n"
        + device_context_str
        + facts_str
        + eq_context_str
    )

    from jojo_journal import context as memory_context
    system_prompt += memory_context(prompt_text)
    attempts = 0
    while attempts < min(2, len(GEMINI_KEYS)):
        attempts += 1
        active_key = GEMINI_KEYS[current_gemini_index]
        client = make_client(api_key=active_key)

        try:
            # Chats API pattern prevents AFC warning and latency
            chat = client.chats.create(
                model=MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.6,
                    thinking_config=types.ThinkingConfig(thinking_level="low") if MODEL.startswith("gemini-3") else None,
                    max_output_tokens=400
                )
            )
            response = chat.send_message(prompt_text)
            reply = (response.text or "").strip()
            if reply:
                threading.Thread(target=save_memory_and_cache, args=(prompt_text, reply), daemon=True).start()
                return reply
            raise RuntimeError("Model returned an empty answer")
        except Exception as err:
            print(f"⚠️ Gemini Key {current_gemini_index + 1} Error: {err}")
            current_gemini_index = (current_gemini_index + 1) % max(1, len(GEMINI_KEYS))
        finally:
            client.close()

    set_outcome("failed")
    return "AI se jawab nahi mil paya. Internet, API key ya model service check kijiye; aapka request complete nahi hua."

def is_agentic_request(text: str) -> bool:
    """Detects whether a command requires autonomous cognitive agent tools (coding, web, files, multi-step) or simple reflex chat."""
    t = text.lower().strip()
    simple_greetings = [
        "hi", "hello", "hey", "kaise ho", "kya haal hai", "good morning",
        "good evening", "good night", "kya chal raha hai", "kya ho raha hai",
        "kaise ho bhai", "namaste", "pranam", "kya haal", "sab badhiya",
        "bore ho raha hu", "joke sunao", "chutkula sunao", "hasao",
        "tum kaun ho", "who are you", "tera naam kya hai", "kisne banaya"
    ]
    if any(t == g or t == g + " jojo" or t == "jojo " + g for g in simple_greetings):
        return False

    agentic_triggers = [
        "script", "code", "python", "powershell", "cmd", "terminal", "command",
        "file", "folder", "desktop", "directory", "save kr", "save kar", "save karo",
        "search", "google", "dhundh", "dhoondh", "internet", "web", "online",
        "calculate", "hisab", "math", "screen", "analyze", "dekh", "padh", "read",
        "bana", "likh", "create", "download", "summary", "extract", "organize",
        "run kr", "run kar", "chala", "execute", "check kr", "check kar", "test kr",
        "skill", "yaad rakh", "memory me daal", "memory mai", "automate",
        "aur", "then", "uske baad", "phir", "open karke", "kholke", "usme"
    ]
    if any(k in t for k in agentic_triggers):
        return True
    if len(t.split()) >= 5:
        return True
    return False

# ==========================================
# 🔒 4. STRICT FINANCIAL & CRYPTOCURRENCY SECURITY SHIELD
# ==========================================
SECURITY_REFUSAL_MSG = "अरे नहीं बॉस, ये पेमेंट्स, OTP या क्रिप्टो वॉलेट्स (MetaMask, Binance आदि) से जुड़ा है! आपकी सुरक्षा के लिए मैं इसे कभी हाथ नहीं लगाऊँगा।"

FINANCIAL_BLACKLIST = [
    # 🏦 Banking & Traditional Payments
    "otp", "one time password", "cvv", "upi pin", "atm pin",
    "gpay", "google pay", "phonepe", "paytm", "bhim", "cred",
    "yono", "bank account", "netbanking", "send money", "transfer money",
    "card number", "debit card", "credit card", "banking app", "bhim upi",
    "password change", "pin change", "पैसे भेजो", "ओटीपी", "बैंक",

    # 🪙 Cryptocurrency Wallets (Web3 / Desktop / Mobile)
    "metamask", "meta mask", "मेटामास्क",
    "trustwallet", "trust wallet", "ट्रस्ट वॉलेट",
    "phantom", "phantom wallet",
    "coinbase wallet", "coinbase",
    "exodus", "exodus wallet",
    "rabby", "rabby wallet",
    "rainbow wallet", "rainbow",
    "zerion", "safepal",
    "ledger", "ledger live", "trezor",
    "bitkeep", "ronin wallet", "ronin",
    "solflare", "sui wallet", "keplr", "argent",
    "crypto wallet", "cryptocurrency wallet", "web3 wallet", "defi wallet",
    "crypto app", "क्रिप्टो वॉलेट", "क्रिप्टो",

    # 📈 Crypto Exchanges & Trading Platforms
    "binance", "बायनेंस", "बाइनेंस",
    "bitget", "बिटगेट",
    "bybit", "बायबिट",
    "kucoin", "कूकॉइन",
    "kraken",
    "coindcx", "coin dcx",
    "wazirx", "वज़ीरएक्स",
    "coinswitch", "coin switch", "coinswitch kuber",
    "mudrex", "gate.io", "gate io",
    "mexc", "htx", "huobi", "crypto.com",
    "crypto exchange", "crypto trading",

    # 🔑 Private Keys, Seed Phrases & Sensitive Blockchain Actions
    "seed phrase", "recovery phrase", "secret recovery phrase", "mnemonic",
    "private key", "private keys", "secret key",
    "12 word", "12 words", "24 word", "24 words", "seed words",
    "crypto transfer", "send crypto", "crypto send",
    "send btc", "send eth", "send usdt", "send sol", "send bitcoin",
    "crypto withdrawal", "withdraw crypto", "crypto deposit",
    "सीड फ्रेज", "प्राइवेट की", "क्रिप्टोकरेंसी"
]

def is_safe_command(text):
    from jojo_policy import blocked_reason
    if blocked_reason(text):
        return False
    t = text.lower()
    for w in FINANCIAL_BLACKLIST:
        if len(w) <= 4:
            if re.search(r'\b' + re.escape(w) + r'\b', t):
                return False
        else:
            if w in t:
                return False
    return True

def add_local_note(note_text):
    n_id = None
    ts = time.time()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO notes (text, created_at) VALUES (?, ?)", (note_text, ts))
        n_id = c.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Note Save Error: {e}")
    if db is not None:
        try:
            db.collection("notes").add({"text": note_text, "created_at": firestore.SERVER_TIMESTAMP})
        except Exception:
            pass
    return n_id

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

def open_url_in_chrome(url=None):
    """Launches Chrome or default browser with the given URL robustly."""
    from jojo_policy import guard_desktop
    guard_desktop(url or '')
    try:
        launched = False
        # Try direct Chrome exe path first
        if os.path.exists(CHROME_PATH):
            try:
                if url:
                    subprocess.Popen([CHROME_PATH, url], shell=False)
                else:
                    subprocess.Popen([CHROME_PATH], shell=False)
                launched = True
                print(f"✅ Chrome launched: {url or 'homepage'}")
            except Exception as e:
                print(f"⚠️ Chrome direct launch failed: {e}")

        # Fallback: use Windows 'start' command (opens default browser)
        if not launched:
            try:
                if url:
                    os.startfile(url)
                else:
                    subprocess.Popen(['cmd', '/c', 'start chrome'], shell=True)
                launched = True
                print(f"✅ Browser opened via startfile: {url or 'chrome'}")
            except Exception as e:
                print(f"⚠️ startfile fallback failed: {e}")

        # Last resort: PowerShell
        if not launched:
            try:
                target = url if url else "https://www.google.com"
                subprocess.Popen(['powershell', '-Command', f'Start-Process "{target}"'], shell=False)
                print(f"✅ Browser opened via PowerShell: {target}")
            except Exception as e:
                print(f"⚠️ PowerShell fallback failed: {e}")

        time.sleep(0.5)
        # Try to bring Chrome window to foreground
        try:
            import win32gui, win32con
            def enum_chrome(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "Chrome" in title or "Google Chrome" in title or "Edge" in title:
                        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                        win32gui.SetForegroundWindow(hwnd)
            win32gui.EnumWindows(enum_chrome, None)
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️ open_url_in_chrome Error: {e}")

def extract_shopping_query(text):
    fillers = [
        "google chrome", "chrome", "chomr", "crom", "crome", "क्रोम", "क्रॉम",
        "amazon.in", "amazon", "अमेज़न", "shopping", "flipkart", "फ्लिपकार्ट",
        "open karke", "open krke", "open karo", "open kar", "open", "kholo", "kholna", "khol do", "khol",
        "search karke", "search karo", "search kar", "search", "dhundo", "dhoondo",
        "dikhao", "dikha", "dekh", "dekho", "dekhna",
        "par", "pe", "per", "mein", "mai", "me", "se", "ko", "bhi", "aur", "and"
    ]
    cleaned = text.lower()
    for f in sorted(fillers, key=len, reverse=True):
        cleaned = re.sub(r'\b' + re.escape(f) + r'\b', ' ', cleaned)
    hindi_fillers = ["खोलो", "खोल", "सर्च", "ढूंढो", "दिखाओ", "दिखा", "देखो", "पर", "में", "और", "करके", "करो", "कर"]
    for hf in hindi_fillers:
        cleaned = cleaned.replace(hf, " ")
    return re.sub(r'\s+', ' ', cleaned).strip()

def extract_youtube_query(text):
    fillers = [
        "google chrome", "chrome", "यूट्यूब", "youtube", "yt",
        "open karke", "open krke", "open karo", "open kar", "open", "kholo",
        "play karo", "play kar", "play", "chalao", "chala do", "chala de", "chala", "lagao", "laga do", "laga", "bajao", "baja",
        "search karke", "search karo", "search kar", "search",
        "par", "pe", "per", "mein", "mai", "me", "ke", "ka", "ki", "ko", "gana", "gaana", "song", "songs", "video", "videos"
    ]
    cleaned = text.lower()
    for f in sorted(fillers, key=len, reverse=True):
        cleaned = re.sub(r'\b' + re.escape(f) + r'\b', ' ', cleaned)
    hindi_fillers = ["यूट्यूब", "गाना", "गाने", "सॉन्ग", "चलाओ", "चला", "लगाओ", "लगा", "बजाओ", "बजा", "पर", "में", "खोल", "खोलो"]
    for hf in hindi_fillers:
        cleaned = cleaned.replace(hf, " ")
    return re.sub(r'\s+', ' ', cleaned).strip()

def open_windows_settings(subpath=""):
    """
    Opens Windows Settings using native os.startfile (ShellExecute) with rock-solid fallbacks.
    Guaranteed to actually launch SystemSettings.exe!
    """
    uri = f"ms-settings:{subpath}".strip()
    try:
        os.startfile(uri)
        print(f"✅ Windows Settings launched via os.startfile: {uri}")
        return True
    except Exception as e:
        print(f"⚠️ os.startfile failed for {uri}: {e}")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-Command", f'Start-Process "{uri}"'], shell=False)
        print(f"✅ Windows Settings launched via PowerShell: {uri}")
        return True
    except Exception as e2:
        print(f"⚠️ PowerShell fallback failed: {e2}")
    try:
        subprocess.Popen(f'start "" "{uri}"', shell=True)
        return True
    except Exception:
        pass
    return False

PS_HARDWARE_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "jojo_hardware_control.ps1"))

def control_hardware(target: str, action: str, value: int = 50):
    """
    Direct Windows native hardware controller via WinRT Radio & CIM APIs.
    Controls Bluetooth, WiFi state seamlessly without touching UI.
    """
    try:
        cmd = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", PS_HARDWARE_SCRIPT,
            "-Target", target,
            "-Action", action,
            "-Value", str(value)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=16)
        out = res.stdout.strip()
        print(f"⚡ [Hardware {target.upper()}]: Action '{action}' -> {out}")
        ok = res.returncode == 0 and not out.startswith("ERROR:")
        if not ok:
            set_outcome("failed")
        return ok, out or res.stderr.strip()
    except Exception as e:
        print(f"⚠️ Hardware control error ({target}:{action}): {e}")
        return False, str(e)

def get_laptop_brightness() -> int:
    """Returns current display brightness percentage (0-100)."""
    try:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        return int(res.stdout.strip())
    except Exception as exc:
        raise RuntimeError("Unable to read this display's brightness") from exc

def set_laptop_brightness(level: int) -> bool:
    """Sets display brightness directly via WMI methods."""
    try:
        level = max(0, min(100, int(level)))
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        return res.returncode == 0
    except Exception:
        return False

def execute_pc_tasks(text_command, source: str = None):
    from jojo_device_lock import desktop_command
    lock_reply=desktop_command(text_command,source or 'laptop')
    if lock_reply is not None:return lock_reply
    if not is_safe_command(text_command):
        return SECURITY_REFUSAL_MSG
    cmd = text_command.lower().strip()

    # 🧠 SMART DEVICE CONTEXT DETECTION — 3-Layer Intelligence
    # Layer 1: Explicit source from API caller ('laptop' or 'mobile')
    # Layer 2: Global ACTIVE_DEVICE (set by last API call or voice loop)
    # Layer 3: Text cues in the command itself

    # Text-based explicit signals
    is_explicitly_mobile = any(k in cmd for k in [
        "mobile me", "phone me", "mobile mein", "phone mein",
        "mobile par", "phone par", "फ़ोन में", "मोबाइल में",
        "mobile ki", "phone ki", "apne phone", "apne mobile",
        "android me", "android par"
    ])
    is_explicitly_pc = any(k in cmd for k in [
        "laptop", "pc", "computer", "windows", "desktop",
        "laptop me", "laptop par", "laptop ki", "laptop mein"
    ])

    # Determine final device:
    # Priority 1: Explicit speech keywords ('laptop me...' vs 'phone me...')
    if is_explicitly_pc and not is_explicitly_mobile:
        use_mobile = False
    elif is_explicitly_mobile and not is_explicitly_pc:
        use_mobile = True
    # Priority 2: Caller's source device (e.g. laptop microphone vs mobile PWA)
    elif source == "mobile":
        use_mobile = True
    elif source == "laptop":
        use_mobile = False
    # Priority 3: Globally tracked active device
    else:
        use_mobile = (get_active_device() == "mobile")

    # 1. 🛡️ Strict Financial & OTP Security Barrier
    if not is_safe_command(text_command):
        return SECURITY_REFUSAL_MSG

    # 📱 Mobile AI Vision & Controls (ADB / Remote Android)
    if use_mobile:
        mob_cmd = re.sub(r'^(mobile me|phone me|mobile mein|phone mein|mobile par|phone par|mobile ki|phone ki|apne phone|apne mobile|फ़ोन में|मोबाइल में|\s)+', '', cmd).strip()

        # Mobile Screenshot
        if any(k in mob_cmd for k in ["screenshot", "स्क्रीनशॉट"]):
            im, data = jmv.capture_mobile_screen()
            if data:
                desk = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop", "mobile_screenshot.png")
                with open(desk, "wb") as f:
                    f.write(data)
                return "मोबाइल स्क्रीनशॉट डेस्कटॉप पर सेव कर दिया बॉस! 📸"
            return "बॉस, मोबाइल स्क्रीनशॉट नहीं ले पाया! चेक करें कि मोबाइल कनेक्टेड और स्क्रीन ऑन है।"

        # Mobile Allow / Deny / OK / Cancel
        if any(k in mob_cmd for k in ["allow", "अनुमति"]):
            ok, msg = jmv.ai_mobile_click_element("Allow")
            return msg
        if any(k in mob_cmd for k in ["deny", "अस्वीकार", "dont allow"]):
            ok, msg = jmv.ai_mobile_click_element("Deny")
            return msg
        if any(k in mob_cmd for k in ["cancel", "रद्द"]):
            ok, msg = jmv.ai_mobile_click_element("Cancel")
            return msg

        # Mobile Wi-Fi Settings
        if any(k in mob_cmd for k in ["wifi", "wi-fi", "वाईफाई"]):
            adb = jmv.get_adb_executable()
            if adb and jmv.is_adb_connected():
                subprocess.run([adb, "shell", "am", "start", "-a", "android.settings.WIFI_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "मोबाइल WiFi सेटिंग्स खोल दिया बॉस! 📶"
            elif jmv.is_android_device():
                subprocess.run(["am", "start", "-a", "android.settings.WIFI_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "मोबाइल WiFi सेटिंग्स खोल दिया बॉस! 📶"
            return "बॉस, मोबाइल WiFi सेटिंग्स खोलने के लिए फोन कनेक्ट होना चाहिए।"

        # Mobile Bluetooth & Settings
        if any(k in mob_cmd for k in ["bluetooth", "ब्लूटूथ"]):
            adb = jmv.get_adb_executable()
            if adb and jmv.is_adb_connected():
                subprocess.run([adb, "shell", "am", "start", "-a", "android.settings.BLUETOOTH_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1.2)
                ok, msg = jmv.ai_mobile_click_element("Bluetooth")
                return f"मोबाइल ब्लूटूथ सेटिंग्स खोल दिया बॉस! {msg}"
            elif jmv.is_android_device():
                subprocess.run(["am", "start", "-a", "android.settings.BLUETOOTH_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1.2)
                ok, msg = jmv.ai_mobile_click_element("Bluetooth")
                return f"मोबाइल ब्लूटूथ सेटिंग्स खोल दिया बॉस! {msg}"
            return "बॉस, मोबाइल ब्लूटूथ के लिए फोन कनेक्टेड होना चाहिए।"

        # Mobile General Settings (e.g. 'setting open kr', 'setting kholo', 'settings')
        if any(k in mob_cmd for k in [
            "setting open", "settings open", "setting kholo", "settings kholo", "setting khol",
            "setting dikha", "सेटिंग खोल", "सेटिंग्स खोल", "setting", "settings", "सेटिंग"
        ]) or re.search(r'\bsettings?\b.*\b(open|khol|dikha|start|launch|on\s+k[ar]+|on|chalu)', mob_cmd):
            adb = jmv.get_adb_executable()
            if adb and jmv.is_adb_connected():
                subprocess.run([adb, "shell", "am", "start", "-a", "android.settings.SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "मोबाइल सेटिंग्स खोल दिया बॉस! 📱⚙️"
            elif jmv.is_android_device():
                subprocess.run(["am", "start", "-a", "android.settings.SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "मोबाइल सेटिंग्स खोल दिया बॉस! 📱⚙️"
            return "बॉस, मोबाइल सेटिंग्स खोलने के लिए फोन USB या WiFi ADB से कनेक्ट होना चाहिए। अगर आप लैपटॉप पर खोलना चाहते हैं तो बोलिए!"

        # Mobile Gestures
        if any(k in mob_cmd for k in ["back", "peeche"]):
            jmv.mobile_keyevent("back")
            return "मोबाइल पर बैक कर दिया बॉस!"
        if any(k in mob_cmd for k in ["home"]):
            jmv.mobile_keyevent("home")
            return "मोबाइल पर होम स्क्रीन खोल दिया बॉस!"
        if any(k in mob_cmd for k in ["scroll down", "niche scroll"]):
            jmv.mobile_swipe(500, 1400, 500, 400)
            return "मोबाइल नीचे स्क्रॉल कर दिया बॉस!"
        if any(k in mob_cmd for k in ["scroll up", "upar scroll"]):
            jmv.mobile_swipe(500, 400, 500, 1400)
            return "मोबाइल ऊपर स्क्रॉल कर दिया बॉस!"

        # General Mobile Click / Select
        m_mob_click = re.search(r'^(?:click\s+on|tap\s+on|select)\s+(.*?)$', mob_cmd)
        if not m_mob_click:
            m_mob_click = re.search(r'^(.*?)\s*(?:option\s+select|select|pe\s+click|click|pe\s+tap|tap)\s*(?:karo|kar|kr)?$', mob_cmd)
        if m_mob_click:
            t = m_mob_click.group(1).strip()
            t = re.sub(r'\s*(option|button|ko|par|pe)+$', '', t).strip()
            if t:
                ok, msg = jmv.ai_mobile_click_element(t)
                return msg

        # Never let an unhandled phone command fall through into Windows actions.
        set_outcome('needs_input')
        return 'Is phone task ke liye native Android JoJo app mein boliye. Laptop par koi action nahi kiya.'

    # 2. 📸 Desktop Screenshot
    if any(k in cmd for k in ["screenshot", "screen shot", "स्क्रीनशॉट", "screen capture", "screen le", "screenshot le", "screenshot lo", "स्क्रीनशॉट लो"]):
        ok, msg = jvc.take_and_save_screenshot()
        if not ok:
            set_outcome("failed")
        return msg

    # 3. ⚙️ Combined Open Setting + Select Sub-option
    # e.g., "setting open kr usme bluetooth option select kr"
    m_combo = re.search(r'(?:setting|सेटिंग)\s*(?:open|खोल).*?(?:usme|me|mein|में)\s*(.*?)\s*(?:option\s+select|select|pe\s+click|click)', cmd)
    if m_combo:
        target = m_combo.group(1).strip()
        target = re.sub(r'^(option|button|ko|par|pe|\s)+', '', target).strip()
        # Open appropriate settings page
        if any(b in target for b in ["bluetooth", "ब्लूटूथ", "device"]):
            open_windows_settings("bluetooth")
        elif any(w in target for w in ["wifi", "wi-fi", "वाईफाई", "network"]):
            open_windows_settings("network-wifi")
        elif any(s in target for s in ["sound", "audio", "साउंड"]):
            open_windows_settings("sound")
        elif any(d in target for d in ["display", "डिस्प्ले"]):
            open_windows_settings("display")
        else:
            open_windows_settings("")
        time.sleep(1.5)
        ok, msg = jvc.ai_click_element(target)
        if not ok:
            set_outcome("failed")
        if ok:
            return f"सेटिंग्स खोलकर {msg}"
        return f"सेटिंग्स खोल दिया बॉस! {msg}"

    # 4. 🎯 Direct Quick Action Clicks (Allow, Deny, Cancel, OK, Yes, No)
    if any(k in cmd for k in ["allow kar", "allow kr", "allow karo", "allow pe click", "allow par click", "allow select", "allow button", "allow daba"]):
        ok, msg = jvc.ai_click_element("Allow")
        if not ok:
            set_outcome("failed")
        return msg
    if any(k in cmd for k in ["deny kar", "deny kr", "deny karo", "deny pe click", "deny par click", "deny select", "dont allow", "don't allow", "अस्वीकार"]):
        ok, msg = jvc.ai_click_element("Deny")
        if not ok:
            set_outcome("failed")
        return msg
    if any(k in cmd for k in ["cancel kar", "cancel pe click", "cancel par click", "cancel karo"]):
        ok, msg = jvc.ai_click_element("Cancel")
        if not ok:
            set_outcome("failed")
        return msg
    if any(k in cmd for k in ["ok kar", "ok pe click", "okay pe click", "ok karo", "okay kar"]):
        ok, msg = jvc.ai_click_element("OK")
        if not ok:
            set_outcome("failed")
        return msg
    if any(k in cmd for k in ["yes pe click", "yes kar", "yes select", "haan pe click"]):
        ok, msg = jvc.ai_click_element("Yes")
        if not ok:
            set_outcome("failed")
        return msg
    if any(k in cmd for k in ["no pe click", "no kar", "no select"]):
        ok, msg = jvc.ai_click_element("No")
        if not ok:
            set_outcome("failed")
        return msg

    # 5. 👁️ Autonomous AI Vision Option Selection & Clicking
    # Matches: "bluetooth option select kr", "bluetooth select kar", "wifi pe click kar", "submit button pe click kar", "click on save"
    m_click1 = re.search(r'^(?:click\s+on|tap\s+on|select)\s+(.*?)$', cmd)
    if m_click1:
        target = m_click1.group(1).strip()
        target = re.sub(r'\s*(option|button|ko|par|pe|karo|kar|kr)+$', '', target).strip()
        if target:
            ok, msg = jvc.ai_click_element(target)
            if not ok:
                set_outcome("failed")
            return msg

    m_click2 = re.search(r'^(.*?)\s*(?:option\s+select|select\s+karo|select\s+kar|select\s+kr|select|चुनो|चुन|pe\s+click|par\s+click|click\s+karo|click\s+kar|click\s+kr)\s*(?:karo|kar|kr)?$', cmd)
    if m_click2:
        target = m_click2.group(1).strip()
        target = re.sub(r'^(isko|use|ye|uss|iss|kripya|please)\s+', '', target).strip()
        target = re.sub(r'\s*(option|button|ko|par|pe)+$', '', target).strip()
        # Avoid false positives on media/tab controls
        if target and not any(ign in target for ign in ["volume", "sound", "aawaz", "gana", "song", "video", "yt", "tab"]):
            ok, msg = jvc.ai_click_element(target)
            if not ok:
                set_outcome("failed")
            return msg

    # 6. ✍️ Direct Text Typing via Clipboard Paste (Supports English & Hindi Unicode)
    m_type = re.search(r'^(?:type\s+kar|type\s+karo|likho|type|write)\s+(.*?)$', cmd)
    if m_type:
        text_val = m_type.group(1).strip()
        if text_val:
            ok, msg = jvc.type_text(text_val)
            if not ok:
                set_outcome("failed")
            return msg

    # 7. ⌨️ Live Keyboard Keys & Shortcuts
    if any(k in cmd for k in ["enter daba", "enter press", "enter maar", "एंटर दबाओ", "enter karo"]):
        return jvc.press_keyboard_key("enter")[1]
    if any(k in cmd for k in ["tab daba", "tab press", "टैब दबाओ", "tab karo"]):
        return jvc.press_keyboard_key("tab")[1]
    if any(k in cmd for k in ["space daba", "space press", "स्पेस दबाओ", "space karo"]):
        return jvc.press_keyboard_key("space")[1]
    if any(k in cmd for k in ["escape daba", "esc press", "esc daba", "escape press"]):
        return jvc.press_keyboard_key("escape")[1]
    if any(k in cmd for k in ["backspace daba", "backspace press", "delete kar", "delete karo"]):
        return jvc.press_keyboard_key("backspace")[1]
    if any(k in cmd for k in ["copy kar", "copy karo"]):
        return jvc.press_keyboard_key("ctrl+c")[1]
    if any(k in cmd for k in ["paste kar", "paste karo"]):
        return jvc.press_keyboard_key("ctrl+v")[1]
    if any(k in cmd for k in ["cut kar", "cut karo"]):
        return jvc.press_keyboard_key("ctrl+x")[1]
    if any(k in cmd for k in ["undo kar", "undo karo"]):
        return jvc.press_keyboard_key("ctrl+z")[1]
    if any(k in cmd for k in ["save kar", "save karo", "file save kar"]):
        return jvc.press_keyboard_key("ctrl+s")[1]
    if any(k in cmd for k in ["select all", "sab select kar", "poora select kar"]):
        return jvc.press_keyboard_key("ctrl+a")[1]
    if any(k in cmd for k in ["alt tab", "switch window", "window badlo", "dusri window"]):
        return jvc.press_keyboard_key("alt+tab")[1]
    if any(k in cmd for k in ["desktop dikhao", "minimize all", "sab minimize"]):
        return jvc.press_keyboard_key("win+d")[1]
    if any(k in cmd for k in ["minimize window", "window choti karo", "window minimize"]):
        return jvc.press_keyboard_key("win+down")[1]
    if any(k in cmd for k in ["maximize window", "window badi karo", "window maximize"]):
        return jvc.press_keyboard_key("win+up")[1]
    if any(k in cmd for k in ["close window", "window band karo", "app band karo"]):
        return jvc.press_keyboard_key("alt+f4")[1]

    # 8. 🖱️ Live Mouse Clicks & Movement
    if any(k in cmd for k in ["double click", "double click kar", "डबल क्लिक"]):
        from jojo_desktop_guard import guard_point
        guard_point(*pyautogui.position())
        pyautogui.doubleClick()
        return "डबल क्लिक कर दिया बॉस!"
    if any(k in cmd for k in ["right click", "right click kar", "राइट क्लिक"]):
        from jojo_desktop_guard import guard_point
        guard_point(*pyautogui.position())
        pyautogui.rightClick()
        return "राइट क्लिक कर दिया बॉस!"
    if any(k in cmd for k in ["left click", "yahan click", "click kar", "क्लिक करो"]) and not any(k in cmd for k in ["pe click", "par click"]):
        from jojo_desktop_guard import guard_point
        guard_point(*pyautogui.position())
        pyautogui.click()
        return "क्लिक कर दिया बॉस!"

    # Mouse movement
    if any(k in cmd for k in ["mouse center", "mouse beech me", "mouse center me"]):
        sw, sh = pyautogui.size()
        pyautogui.moveTo(sw//2, sh//2, duration=0.3)
        return "माउस सेंटर में ले आया बॉस!"
    if any(k in cmd for k in ["mouse thoda upar", "mouse upar le ja"]):
        pyautogui.moveRel(0, -180, duration=0.2)
        return "माउस ऊपर कर दिया बॉस!"
    if any(k in cmd for k in ["mouse thoda niche", "mouse niche le ja"]):
        pyautogui.moveRel(0, 180, duration=0.2)
        return "माउस नीचे कर दिया बॉस!"
    if any(k in cmd for k in ["mouse thoda left", "mouse left le ja"]):
        pyautogui.moveRel(-180, 0, duration=0.2)
        return "माउस लेफ्ट कर दिया बॉस!"
    if any(k in cmd for k in ["mouse thoda right", "mouse right le ja"]):
        pyautogui.moveRel(180, 0, duration=0.2)
        return "माउस राइट कर दिया बॉस!"

    # 9. 📜 Scroll Controls
    if any(k in cmd for k in ["scroll down", "niche scroll", "नीचे स्क्रॉल"]):
        pyautogui.scroll(-700)
        return "नीचे स्क्रॉल कर दिया बॉस!"

    if any(k in cmd for k in ["scroll up", "upar scroll", "ऊपर स्क्रॉल"]):
        pyautogui.scroll(700)
        return "ऊपर स्क्रॉल कर दिया बॉस!"

    # 10. 📑 Tab Controls
    if any(k in cmd for k in ["close tab", "tab band karo", "tab band kar", "tab band", "टैब बंद"]):
        pyautogui.hotkey('ctrl', 'w')
        return "टैब बंद कर दिया बॉस!"

    if any(k in cmd for k in ["new tab", "naya tab kholo", "naya tab", "नया टैब"]):
        pyautogui.hotkey('ctrl', 't')
        return "नया टैब खोल दिया बॉस!"

    if any(k in cmd for k in ["close chrome", "chrome band karo", "chrome band kar", "chrome band", "क्रोम बंद"]):
        os.system("taskkill /F /IM chrome.exe")
        return "क्रोम बंद कर दिया बॉस!"

    if any(k in cmd for k in ["refresh", "reload", "रिफ्रेश", "dobara load"]):
        pyautogui.press('f5')
        return "पेज रिफ्रेश कर दिया बॉस!"

    if any(k in cmd for k in ["full screen", "fullscreen", "बड़ा करो", "maximize"]):
        pyautogui.press('f11')
        return "फुल स्क्रीन कर दिया बॉस!"

    # ==========================================
    # 📶 11. Complete Hardware Controls (Bluetooth, Wi-Fi, Brightness, Volume, Settings)
    # ==========================================

    # A. 📶 BLUETOOTH CONTROL (ON, OFF, TOGGLE, STATUS vs SETTINGS)
    is_bt = any(b in cmd for b in ["bluetooth", "bletooth", "bluetoth", "ब्लूटूथ"])
    if is_bt:
        # 1. Pure Settings window request
        is_bt_setting = any(s in cmd for s in ["setting", "settings", "सेटिंग", "सेटिंग्स"]) and not any(t in cmd for t in ["on", "off", "chalu", "band", "चालू", "बंद"])
        if is_bt_setting or (any(o in cmd for o in ["kholo", "khol", "open", "dikha", "दिखा", "खोल", "ओपन"]) and not any(t in cmd for t in ["on", "off", "chalu", "band", "चालू", "बंद"])):
            ok = open_windows_settings("bluetooth")
            if ok:
                return "ब्लूटूथ सेटिंग्स खोल दिया बॉस! 📶"
            return "बॉस, ब्लूटूथ सेटिंग्स खोलने में दिक्कत आई!"

        # 2. Turn ON
        if any(o in cmd for o in ["on", "chalu", "start", "enable", "activate", "ऑन", "चालू", "शुरू"]) and not any(f in cmd for f in ["off", "band", "बंद", "ऑफ"]):
            ok, msg = control_hardware("bluetooth", "on")
            if ok:
                return "ब्लूटूथ ऑन कर दिया बॉस! 📶"
            open_windows_settings("bluetooth")
            return "बॉस, ब्लूटूथ ऑन करने के लिए सेटिंग्स खोल दी है!"

        # 3. Turn OFF
        if any(f in cmd for f in ["off", "band", "stop", "disable", "deactivate", "ऑफ", "बंद"]):
            ok, msg = control_hardware("bluetooth", "off")
            if ok:
                return "ब्लूटूथ बंद कर दिया बॉस!"
            open_windows_settings("bluetooth")
            return "बॉस, ब्लूटूथ सेटिंग्स खोल दी है, वहां से बंद कर सकते हैं!"

        # 4. Toggle
        if any(t in cmd for t in ["toggle", "switch", "टॉगल", "बदलो"]):
            ok, msg = control_hardware("bluetooth", "toggle")
            if ok:
                return "ब्लूटूथ टॉगल कर दिया बॉस!"
            return "ब्लूटूथ टॉगल नहीं हो पाया बॉस!"

        # 5. Status
        if any(st in cmd for st in ["status", "check", "kaisa", "on hai ya", "स्टेटस", "चेक"]):
            ok, msg = control_hardware("bluetooth", "status")
            if not ok:
                return "⚠️ Could not read bluetooth state: " + msg
            if "On" in msg:
                return "बॉस, ब्लूटूथ अभी ऑन है! 📶"
            return "बॉस, ब्लूटूथ अभी बंद है!"

        # Default fallback for "bluetooth on"
        ok, msg = control_hardware("bluetooth", "on")
        return "ब्लूटूथ ऑन कर दिया बॉस! 📶" if ok else "⚠️ Bluetooth could not be enabled: " + msg

    # B. 🌐 WI-FI CONTROL (ON, OFF, TOGGLE, STATUS vs SETTINGS)
    is_wifi = any(w in cmd for w in ["wifi", "wi-fi", "वाईफाई"])
    if is_wifi:
        is_wifi_setting = any(s in cmd for s in ["setting", "settings", "सेटिंग", "सेटिंग्स"]) and not any(t in cmd for t in ["on", "off", "chalu", "band", "चालू", "बंद"])
        if is_wifi_setting or (any(o in cmd for o in ["kholo", "khol", "open", "dikha", "दिखा", "खोल", "ओपन"]) and not any(t in cmd for t in ["on", "off", "chalu", "band", "चालू", "बंद"])):
            ok = open_windows_settings("network-wifi")
            if ok:
                return "WiFi सेटिंग्स खोल दिया बॉस! 🌐"
            return "बॉस, WiFi सेटिंग्स खोलने में दिक्कत आई!"

        if any(o in cmd for o in ["on", "chalu", "start", "enable", "connect", "ऑन", "चालू", "शुरू"]) and not any(f in cmd for f in ["off", "band", "बंद", "ऑफ", "disconnect"]):
            ok, msg = control_hardware("wifi", "on")
            if ok:
                return "WiFi ऑन कर दिया बॉस! 🌐"
            return "बॉस, WiFi ऑन करने में दिक्कत आई!"

        if any(f in cmd for f in ["off", "band", "stop", "disable", "disconnect", "ऑफ", "बंद"]):
            ok, msg = control_hardware("wifi", "off")
            if ok:
                return "WiFi बंद कर दिया बॉस!"
            return "बॉस, WiFi बंद करने में दिक्कत आई!"

        if any(st in cmd for st in ["status", "check", "स्टेटस", "चेक"]):
            ok, msg = control_hardware("wifi", "status")
            if not ok:
                return "⚠️ Could not read wifi state: " + msg
            if "On" in msg:
                return "बॉस, WiFi रेडियो अभी ऑन है! 🌐"
            return "बॉस, WiFi अभी बंद है!"

        ok, msg = control_hardware("wifi", "on")
        return "WiFi ऑन कर दिया बॉस! 🌐" if ok else "⚠️ WiFi could not be enabled: " + msg

    # C. 🔆 BRIGHTNESS CONTROL (INCREASE, DECREASE, FULL, EXACT %, SETTINGS)
    is_bright = any(b in cmd for b in ["brightness", "ब्राइटनेस", "चमक", "screen light"])
    if is_bright:
        if any(s in cmd for s in ["setting", "सेटिंग"]):
            open_windows_settings("display")
            return "डिस्प्ले और ब्राइटनेस सेटिंग्स खोल दिया बॉस! 🖥️"
        cur_b = get_laptop_brightness()
        if any(u in cmd for u in ["badhao", "badha", "up", "jyada", "tez", "बढ़ाओ", "बढ़ा"]):
            target_b = min(100, cur_b + 20)
            if not set_laptop_brightness(target_b):
                set_outcome("failed")
                return "⚠️ Brightness change could not be confirmed on this display."
            return f"ब्राइटनेस बढ़ा दी बॉस! 🔆 ({target_b}%)"
        if any(d in cmd for d in ["kam", "down", "ghatao", "low", "कम", "घटाओ"]):
            target_b = max(10, cur_b - 20)
            if not set_laptop_brightness(target_b):
                set_outcome("failed")
                return "⚠️ Brightness change could not be confirmed on this display."
            return f"ब्राइटनेस कम कर दी बॉस! 🔅 ({target_b}%)"
        if any(f in cmd for f in ["full", "100", "सौ", "फुल"]):
            if not set_laptop_brightness(100):
                set_outcome("failed")
                return "⚠️ Brightness change could not be confirmed on this display."
            return "ब्राइटनेस 100% फुल कर दी बॉस! 🔆"
        m_num = re.search(r'(\d+)', cmd)
        if m_num:
            target_b = max(0, min(100, int(m_num.group(1))))
            if not set_laptop_brightness(target_b):
                set_outcome("failed")
                return "⚠️ Brightness change could not be confirmed on this display."
            return f"ब्राइटनेस {target_b}% कर दी बॉस! 🔆"
        target_b = min(100, cur_b + 20)
        if not set_laptop_brightness(target_b):
            set_outcome("failed")
            return "⚠️ Brightness change could not be confirmed on this display."
        return f"ब्राइटनेस बढ़ा दी बॉस! 🔆 ({target_b}%)"

    # D. 🖥️ DISPLAY & RESOLUTION SETTINGS
    if any(k in cmd for k in ["display setting", "screen setting", "resolution", "डिस्प्ले सेटिंग"]):
        ok = open_windows_settings("display")
        if ok:
            return "डिस्प्ले सेटिंग्स खोल दिया बॉस! 🖥️"
        return "बॉस, डिस्प्ले सेटिंग्स खोलने में दिक्कत आई!"

    # E. 🔊 SOUND & AUDIO CONTROLS
    if any(k in cmd for k in ["sound setting", "audio setting", "speaker setting", "microphone setting", "साउंड सेटिंग", "ऑडियो सेटिंग"]):
        ok = open_windows_settings("sound")
        if ok:
            return "साउंड सेटिंग्स खोल दिया बॉस! 🔊"
        return "बॉस, साउंड सेटिंग्स खोलने में दिक्कत आई!"

    if any(k in cmd for k in ["volume up", "volume badhao", "aawaz badhao", "sound badhao", "आवाज़ बढ़ाओ", "आवाज बढ़ाओ"]):
        for _ in range(5):
            pyautogui.press('volumeup')
        return "आवाज़ बढ़ा दी बॉस! 🔊"
    if any(k in cmd for k in ["volume down", "volume kam karo", "aawaz kam karo", "sound kam karo", "आवाज़ कम करो", "आवाज कम करो"]):
        for _ in range(5):
            pyautogui.press('volumedown')
        return "आवाज़ कम कर दी बॉस! 🔉"
    if any(k in cmd for k in ["unmute", "अनम्यूट", "aawaz wapas"]):
        pyautogui.press('volumemute')
        pyautogui.press('volumeup')
        return "अनम्यूट कर दिया बॉस! 🔊"
    if any(k in cmd for k in ["mute", "म्यूट", "aawaz band", "आवाज़ बंद"]):
        pyautogui.press('volumemute')
        return "म्यूट कर दिया बॉस! 🔇"

    # F. 📱 APPS SETTING
    if any(k in cmd for k in ["apps setting", "installed apps", "app list", "ऐप सेटिंग", "ऐप्स सेटिंग"]):
        ok = open_windows_settings("appsfeatures")
        if ok:
            return "ऐप्स सेटिंग्स खोल दिया बॉस! 📱"
        return "बॉस, ऐप्स सेटिंग्स खोलने में दिक्कत आई!"

    # G. 🖥️ GENERAL WINDOWS SETTINGS — Full Dual-Script Coverage (English + Devanagari)
    is_setting_intent = (
        any(k in cmd for k in [
            "setting open", "settings open", "setting on", "settings on",
            "setting kholo", "settings kholo", "setting khol", "setting dikha", "settings dikha",
            "open setting", "open settings", "start setting", "launch setting",
            "laptop ki setting", "laptop setting", "pc setting", "windows setting",
            "सेटिंग ओपन", "सेटिंग्स ओपन", "सेटिंग चालू", "सेटिंग खोलो", "सेटिंग खोल", "सेटिंग दिखाओ",
            "सेटिंग ऑन", "ओपन सेटिंग", "लैपटॉप की सेटिंग", "विंडोज़ सेटिंग", "सेटिंग शुरू",
            "सेटिंग चलाओ", "सेटिंग्स खोलो"
        ])
        or bool(re.search(r'(?:setting|settings|सेटिंग|सेटिंग्स).*(?:open|khol|dikha|start|launch|on|chalu|ओपन|खोल|दिखा|चालू|ऑन)', cmd))
        or bool(re.search(r'(?:open|khol|start|launch|ओपन|खोल|चालू).*(?:setting|settings|सेटिंग|सेटिंग्स)', cmd))
        or (cmd in ["setting", "settings", "सेटिंग", "सेटिंग्स"])
    )
    if is_setting_intent:
        ok = open_windows_settings("")
        if ok:
            return "विंडोज़ सेटिंग्स खोल दिया बॉस! 🖥️"
        return "बॉस, सेटिंग्स खोलने में दिक्कत आई!"


    # 12. 📋 Task Manager
    if any(k in cmd for k in ["task manager", "taskmgr", "टास्क मैनेजर", "process dekho", "processor check"]):
        try:
            os.startfile("taskmgr")
        except Exception:
            subprocess.Popen(['taskmgr'], shell=False)
        return "टास्क मैनेजर खोल दिया बॉस!"

    # 13. 📁 File Explorer
    if any(k in cmd for k in ["file explorer", "explorer", "my computer", "files dekho", "folder kholo", "फाइल एक्सप्लोरर", "फाइल देखो"]):
        try:
            os.startfile("explorer")
        except Exception:
            subprocess.Popen(['explorer'], shell=False)
        return "फाइल एक्सप्लोरर खोल दिया बॉस!"

    # 14. 💻 Quick Apps (Notepad, Calculator, VS Code, Paint)
    if any(k in cmd for k in ["notepad", "नोटपैड"]):
        try:
            os.startfile("notepad")
        except Exception:
            subprocess.Popen(['notepad'], shell=False)
        return "नोटपैड खोल दिया बॉस!"
    if any(k in cmd for k in ["calculator", "calc", "कैलकुलेटर", "हिसाब"]):
        try:
            os.startfile("calc")
        except Exception:
            subprocess.Popen(['calc'], shell=False)
        return "कैलकुलेटर खोल दिया बॉस!"
    if any(k in cmd for k in ["vs code", "vscode", "visual studio", "code editor"]):
        try:
            os.startfile("code")
        except Exception:
            subprocess.Popen(['cmd', '/c', 'start "" code'], shell=True)
        return "VS Code खोल दिया बॉस!"
    if any(k in cmd for k in ["paint", "drawing", "पेंट"]):
        try:
            os.startfile("mspaint")
        except Exception:
            subprocess.Popen(['mspaint'], shell=False)
        return "पेंट खोल दिया बॉस!"

    # 17. 🔄 Shutdown / Restart
    if any(k in cmd for k in ["laptop band karo", "pc band karo", "shutdown karo", "बंद करो laptop", "system band"]):
        os.system("shutdown /s /t 10")
        return "बॉस, 10 सेकंड में लैपटॉप बंद हो जाएगा! रुकना है तो बोलना!"
    if any(k in cmd for k in ["restart karo", "reboot", "restart laptop", "रिस्टार्ट करो"]):
        os.system("shutdown /r /t 10")
        return "बॉस, 10 सेकंड में रिस्टार्ट होगा!"
    if any(k in cmd for k in ["shutdown cancel", "band mat karo", "ruk jao"]):
        os.system("shutdown /a")
        return "बॉस, शटडाउन कैंसल कर दिया!"

    # 11. 📝 Quick Notes
    if any(k in cmd for k in ["note likho", "नोट लिखो", "save note", "नोट बनाओ"]):
        note_content = re.sub(r'^(note likho|नोट लिखो|save note|नोट बनाओ|likho|लिखो|note|नोट|:|\s)+', '', text_command, flags=re.IGNORECASE).strip()
        if note_content:
            add_local_note(note_content)
            return f"नोट सेव कर लिया बॉस: '{note_content}'"
        return "नोट में क्या लिखना है बॉस?"

    # 12. 📞 Phone Calling Guidance
    if any(k in cmd for k in ["call karo", "कॉल करो", "phone lagao", "फ़ोन लगाओ"]):
        return "बॉस, फ़ोन कॉलिंग के लिए JoJo मोबाइल ऐप या Termux कनेक्टेड होना चाहिए!"

    # 13. 🛒 Amazon Shopping & Products Search
    is_amazon_intent = any(k in cmd for k in ["amazon", "अमेज़न", "shopping", "खरीद", "flipkart", "फ्लिपकार्ट"])
    is_product_intent = any(k in cmd for k in ["shirt", "tshirt", "t-shirt", "dress", "jeans", "shoes", "sneakers", "watch", "hoodie", "jacket", "kurta", "शर्ट", "टीशर्ट", "ड्रेस", "जींस", "जूते"])
    if is_amazon_intent or (is_product_intent and any(v in cmd for v in ["dekh", "dikha", "search", "kholo", "dekho", "dikhana"])):
        clean_q = extract_shopping_query(text_command)
        flipkart = 'flipkart' in cmd or 'फ्लिपकार्ट' in cmd
        shop = 'Flipkart' if flipkart else 'Amazon'
        base = 'https://www.flipkart.com' if flipkart else 'https://www.amazon.in'
        if clean_q:
            url = base + ('/search?q=' if flipkart else '/s?k=') + urllib.parse.quote(clean_q)
            open_url_in_chrome(url)
            return f"{shop} par {clean_q} ka search kholne ka request bheja hai."
        else:
            open_url_in_chrome(base)
            return f"Chrome mein {shop} kholne ka request bheja hai. Kya dhoondhna hai?"

    # 14. 📺 YouTube & Music Streaming
    if any(k in cmd for k in ["youtube", "yt", "यूट्यूब", "gana", "gaana", "song", "songs", "video"]):
        yt_q = extract_youtube_query(text_command)
        if yt_q:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_q)}"
            open_url_in_chrome(url)
            return f"हाँ बॉस! यूट्यूब पर {yt_q} चला दिया है!"
        else:
            open_url_in_chrome("https://www.youtube.com")
            return "यूट्यूब खोल दिया है बॉस!"

    # 15. 🌐 Google Search
    if any(k in cmd for k in ["google search", "google par search", "google par dhundo", "google par", "गूगल पर"]):
        clean_search = re.sub(r'^(google search|google par search karo|google par search kar|google par search|google par|google|\s)+', '', cmd).strip()
        if clean_search:
            open_url_in_chrome(f"https://www.google.com/search?q={urllib.parse.quote(clean_search)}")
            return f"गूगल पर {clean_search} ढूँढ दिया बॉस!"
        else:
            open_url_in_chrome("https://www.google.com")
            return "गूगल खोल दिया बॉस!"

    # 16. 🌐 Google Chrome Direct Open
    if any(k in cmd for k in ["chrome", "google chrome", "क्रोम", "chomr", "crom", "chorme", "crome", "क्रॉम", "chrome kholo", "chrome open"]):
        open_url_in_chrome()
        return "गूगल क्रोम खोल दिया बॉस!"

    # 17. 🗺️ Google Maps & Navigation
    if any(k in cmd for k in ["map", "maps", "मैप", "मैप्स", "rasta", "रास्ता", "navigate", "direction"]):
        clean_dest = re.sub(r'^(open|kholo|search|par|ka|to|se|rasta|maps|मैप|रास्ता|navigate|direction|\s)+', '', cmd).strip()
        if clean_dest:
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(clean_dest)}"
            open_url_in_chrome(url)
            return f"गूगल मैप्स पर {clean_dest} का रास्ता खोल दिया है बॉस!"
        else:
            open_url_in_chrome("https://www.google.com/maps")
            return "गूगल मैप्स खोल दिया है बॉस!"

    return None

# ==========================================
# 🎙️ 5. JOJO NEURAL VOICE ENGINE (VOICE 2: MADHUR ENERGETIC BUDDY + FALLBACK)
# ==========================================
voice_lock = threading.Lock()
is_speaking = False

# Voice 2 selected by Boss: Microsoft Madhur Neural (+10% speed, +4Hz pitch) - PERMANENT ONLY
CURRENT_VOICE_ENGINE = "voice_2_madhur"
VOICE_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "voice_cache"))
os.makedirs(VOICE_CACHE_DIR, exist_ok=True)

VOICE_PARAMS = {
    "voice": "hi-IN-MadhurNeural",
    "rate": "+10%",
    "pitch": "+4Hz"
}

def get_cached_speech_path(text):
    clean = text.strip()
    h = hashlib.md5(clean.encode("utf-8")).hexdigest()
    path = os.path.join(VOICE_CACHE_DIR, f"{h}.mp3")
    if os.path.exists(path) and os.path.getsize(path) > 400:
        return path
    return None

def _run_async_safe(coro):
    """Safely run an async coroutine from sync code, even if an event loop exists."""
    try:
        # Try to get running loop — if exists, run in new thread
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(asyncio.run, coro)
                return future.result(timeout=15)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop — create fresh one
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

async def synthesize_madhur_audio(text, out_path):
    import edge_tts
    last_err = None
    for attempt in range(3):
        try:
            comm = edge_tts.Communicate(text, VOICE_PARAMS["voice"], rate=VOICE_PARAMS["rate"], pitch=VOICE_PARAMS["pitch"])
            await comm.save(out_path)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 400:
                return True
        except Exception as e:
            last_err = e
            await asyncio.sleep(0.25 * (attempt + 1))

    # Fallback retry without rate/pitch if parameter was rejected
    try:
        comm = edge_tts.Communicate(text, VOICE_PARAMS["voice"])
        await comm.save(out_path)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 400:
            return True
    except Exception as e:
        last_err = e

    print(f"⚠️ Voice 2 Synthesis Error: {last_err}")
    return False

def synthesize_sync(text, out_path):
    """Synchronous wrapper for TTS synthesis — never crashes on event loop conflicts."""
    async def bounded():
        return await asyncio.wait_for(synthesize_madhur_audio(text, out_path), timeout=18)
    return _run_async_safe(bounded())

def split_text_to_chunks(text, max_chars=200):
    """Split long text into natural speech chunks at sentence boundaries."""
    # Split at sentence endings
    import re
    sentences = re.split(r'(?<=[।!?\n.])\s*', text.strip())
    chunks = []
    current = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            # If single sentence too long, split by comma
            if len(s) > max_chars:
                parts = re.split(r'(?<=[,;])\s*', s)
                sub = ""
                for p in parts:
                    if len(sub) + len(p) + 1 <= max_chars:
                        sub = (sub + " " + p).strip()
                    else:
                        if sub: chunks.append(sub)
                        sub = p
                if sub: chunks.append(sub)
                current = ""
            else:
                current = s
    if current:
        chunks.append(current)
    return chunks if chunks else [text]

winmm = ctypes.windll.winmm

def play_audio_file(file_path, timeout=15.0):
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path) or os.path.getsize(abs_path) < 100:
        return False

    # Method 1 (Primary & 100% Reliable): Direct WASAPI/DirectSound via soundfile + sounddevice to active Speakers
    try:
        data, fs = sf.read(abs_path)
        sd.play(data, fs)
        timeout = max(timeout, len(data) / float(fs) + 3.0)
        start_t = time.time()
        while sd.get_stream() and sd.get_stream().active:
            if speech_cancel.is_set() or time.time() - start_t > timeout:
                sd.stop()
                return bool(speech_cancel.is_set())
            time.sleep(0.03)
        return True
    except Exception as e:
        print(f"⚠️ sounddevice playback error: {e}")

    # Method 2 (MCI Fallback): winmm with maximum volume
    try:
        winmm.mciSendStringW('close jojo_audio', None, 0, None)
        ret = winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias jojo_audio', None, 0, None)
        if ret == 0:
            winmm.mciSendStringW('setaudio jojo_audio volume to 1000', None, 0, None)
            def _worker():
                winmm.mciSendStringW('play jojo_audio wait', None, 0, None)
                winmm.mciSendStringW('close jojo_audio', None, 0, None)
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            length_buf = ctypes.create_unicode_buffer(64)
            winmm.mciSendStringW('status jojo_audio length', length_buf, 64, None)
            try:
                timeout = max(timeout, int(length_buf.value) / 1000 + 3)
            except ValueError:
                timeout = max(timeout, 45)
            deadline = time.monotonic() + timeout
            while t.is_alive() and not speech_cancel.is_set() and time.monotonic() < deadline:
                t.join(timeout=.1)
            if t.is_alive():
                try:
                    winmm.mciSendStringW('stop jojo_audio', None, 0, None)
                    winmm.mciSendStringW('close jojo_audio', None, 0, None)
                except Exception:
                    pass
            return True
    except Exception as e:
        print(f"⚠️ MCI playback error: {e}")

    return False


overlay_proc = None

def auto_trigger_desktop_hud():
    """Instantly launches the 3D Holographic HUD floating window on desktop if not running."""
    global overlay_proc
    if os.environ.get("JOJO_NO_OVERLAY") == "1":
        return
    try:
        if overlay_proc is None or overlay_proc.poll() is not None:
            py_exe = sys.executable
            pyw_exe = os.path.join(os.path.dirname(py_exe), "pythonw.exe")
            target_exe = pyw_exe if os.path.exists(pyw_exe) else py_exe
            overlay_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jojo_overlay.py")
            if os.path.exists(overlay_script):
                overlay_proc = subprocess.Popen(
                    [target_exe, overlay_script],
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("🔮 [JoJo 3D Holographic Desktop HUD Active!]")
    except Exception as e:
        print(f"⚠️ Could not auto-launch desktop HUD: {e}")

is_active_session = False
last_interaction_time = 0
SESSION_TIMEOUT = int(read_preferences().get("session_timeout", 120))

voice_state_lock = threading.Lock()
voice_state = {
    "status": "sleeping", # sleeping | wake_detected | authenticating | boss_verified | access_denied | listening | speaking
    "speaker": "none",   # none | boss | stranger
    "last_transcript": "",
    "last_reply": "",
    "active_session": False,
    "boss_similarity": 0.0,
    "timestamp": time.time()
}

def update_voice_state(status=None, speaker=None, transcript=None, reply=None, similarity=None, active=None):
    with voice_state_lock:
        if status is not None:
            voice_state["status"] = status
        if speaker is not None:
            voice_state["speaker"] = speaker
        if transcript is not None:
            voice_state["last_transcript"] = transcript
        if reply is not None:
            voice_state["last_reply"] = reply
        if similarity is not None:
            voice_state["boss_similarity"] = round(float(similarity), 3)
        if active is not None:
            voice_state["active_session"] = bool(active)
        voice_state["timestamp"] = time.time()

last_speaking_time = 0

def _speak_now(text, engine=None):
    global is_speaking, is_active_session, last_speaking_time
    clean_text = text.replace("*", "").replace("#", "").replace("`", "")\
                     .replace('"', '').replace("'", "").strip()

    if not clean_text:
        return

    print(f"JoJo (Voice 2 Madhur): {clean_text}")
    update_voice_state(status="speaking", reply=clean_text)

    acquired = voice_lock.acquire()
    speech_cancel.clear()
    try:
        is_speaking = True
        last_speaking_time = time.time()
        try:
            # 1. Synthesize whole sentence at once for smooth, continuous, non-stop speech
            # This completely eliminates mid-speech freezing, stuttering, and chunk delays!
            if len(clean_text) <= 450:
                chunks = [clean_text]
            else:
                chunks = split_text_to_chunks(clean_text, max_chars=350)

            for chunk in chunks:
                if speech_cancel.is_set():
                    break
                if not chunk.strip():
                    continue

                played = False
                # 1. Check cache first (0ms instant playback)
                cached_file = get_cached_speech_path(chunk)
                if cached_file:
                    played = play_audio_file(cached_file)
                    if played:
                        continue

                # 2. Synthesize with Voice 2 (safe async wrapper)
                h = hashlib.md5(chunk.encode("utf-8")).hexdigest()
                target_path = os.path.join(VOICE_CACHE_DIR, f"{h}.mp3")

                try:
                    success = synthesize_sync(chunk, target_path)
                    if speech_cancel.is_set():
                        break
                except Exception as synth_err:
                    print(f"⚠️ TTS Synthesis Exception: {synth_err}")
                    success = False

                if success and os.path.exists(target_path) and os.path.getsize(target_path) > 400:
                    played = play_audio_file(target_path)

                # 3. Fallback: pyttsx3 offline TTS if playback did not succeed
                if not played:
                    try:
                        fallback = subprocess.Popen([sys.executable, str(ROOT / "jojo_speech_fallback.py")],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                        fallback.stdin.write(chunk.encode("utf-8"))
                        fallback.stdin.close()
                        deadline = time.monotonic() + min(120, max(20, len(chunk) / 8))
                        while fallback.poll() is None:
                            if speech_cancel.is_set() or time.monotonic() > deadline:
                                fallback.terminate()
                                fallback.wait(timeout=3)
                                break
                            time.sleep(.1)
                        if fallback.returncode:
                            report_audio_error("Offline speech failed; the full reply is visible in the desktop window.")
                    except Exception as fb_err:
                        print(f"⚠️ All TTS failed for chunk: {fb_err}")

        except Exception as e:
            print(f"⚠️ Speak Error: {e}")
    finally:
        time.sleep(0.12)
        is_speaking = False
        last_speaking_time = time.time()
        update_voice_state(status="listening" if is_active_session else "sleeping")
        if acquired:
            try:
                voice_lock.release()
            except Exception:
                pass


# ==========================================
# 🛡️ 6. CONTINUOUS BIOMETRIC VOICE FREQUENCY ENGINE
# ==========================================
_preferences = read_preferences()
AUDIO_DEVICE_ID = _preferences.get("audio_device_id")
microphone_paused = threading.Event()
speech_cancel = threading.Event()
shutdown_requested = threading.Event()
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
BOSS_PROFILE_FILE = str(DATA_DIR / "boss_voice_profile.npy")
BOSS_SIMILARITY_THRESHOLD = float(_preferences.get("boss_threshold", 0.65))

# Calibrated physical frequency grid in Hertz (80Hz to 1250Hz covers human pitch & vocal tract formants)
TARGET_FREQ_GRID = np.arange(30) * (44100.0 / 1024.0)

from jojo_speaker import SpeakerVerifier
voice_verifier = SpeakerVerifier()
boss_profile = voice_verifier.profile


def extract_features(mono_audio, sr=AUDIO_SAMPLE_RATE):
    """
    Extracts frequency-calibrated vocal signature independent of hardware sample rate.
    Captures:
    1. Spectral Centroid (vocal tract brightness)
    2. Peak fundamental frequency (pitch)
    3. Multi-band formant energy distribution across human speech bands
    """
    audio = mono_audio.astype(np.float32)
    if np.max(np.abs(audio)) > 0:
        audio = audio / np.max(np.abs(audio))
    nperseg = min(1024, len(audio))
    freqs, psd = signal.welch(audio, sr, nperseg=nperseg)
    psd_interp = np.interp(TARGET_FREQ_GRID, freqs, psd)
    psd_norm = psd_interp / (np.linalg.norm(psd_interp) + 1e-10)
    sc = (np.sum(freqs * psd) / (np.sum(psd) + 1e-10)) / 4000.0
    pf = freqs[np.argmax(psd)] / 2000.0
    feat = np.hstack(([sc, pf], psd_norm))
    return feat / (np.linalg.norm(feat) + 1e-10)

class BiometricResult(tuple):
    def __new__(cls, is_match: bool, similarity: float):
        return super().__new__(cls, (bool(is_match), float(similarity)))
    def __bool__(self):
        return self[0]
    @property
    def is_match(self):
        return self[0]
    @property
    def similarity(self):
        return self[1]

def verify_boss(mono_audio, threshold=None):
    if boss_profile is None or mono_audio is None:
        return BiometricResult(False, 0.0)
    matched, similarity = voice_verifier.verify(mono_audio, threshold=BOSS_SIMILARITY_THRESHOLD if threshold is None else threshold)
    return BiometricResult(matched, similarity)


def audio_base64_to_mono_samples(b64_str):
    try:
        if len(b64_str) > 3_000_000:
            return None, 0
        raw_bytes = base64.b64decode(b64_str, validate=True)
        try:
            with wave.open(io.BytesIO(raw_bytes), 'rb') as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                dtype = np.int16 if sampwidth == 2 else np.int32
                data = np.frombuffer(frames, dtype=dtype)
                if n_channels > 1:
                    data = data.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
                return data, framerate
        except Exception:
            data = np.frombuffer(raw_bytes, dtype=np.int16)
            return data, AUDIO_SAMPLE_RATE
    except Exception as e:
        print(f"⚠️ Audio Base64 Decode Error: {e}")
        return None, 0

def enroll_boss_voice(duration=9):
    global boss_profile, AUDIO_DEVICE_ID
    print(f"🎤 [Recording Boss Voice from Device {AUDIO_DEVICE_ID} for {duration}s...]")
    was_paused = microphone_paused.is_set()
    microphone_paused.set()
    stop_speech()
    if vad_listener is not None:
        vad_listener.close()
    try:
        device_info = sd.query_devices(AUDIO_DEVICE_ID, 'input')
        capture_rate = int(device_info['default_samplerate'])
        recording = sd.rec(
            int(duration * capture_rate),
            samplerate=capture_rate,
            channels=1,
            dtype='int16',
            device=AUDIO_DEVICE_ID
        )
        sd.wait()
        mono_audio = recording.flatten().astype(np.int16)
        if capture_rate != AUDIO_SAMPLE_RATE:
            mono_audio = signal.resample_poly(mono_audio.astype(float), AUDIO_SAMPLE_RATE, capture_rate).astype(np.int16)
        if float(np.sqrt(np.mean(mono_audio.astype(float) ** 2))) < 180:
            return False, "Recording was too quiet. Speak clearly and try enrollment again."
        profile = voice_verifier.enroll(mono_audio)
        boss_profile = profile
        print("🔒 Boss Voice Successfully Enrolled & Profile Saved to Disk!")
        from jojo_user_config import owner
        return True, owner()['name'] + ", aapki voice profile save ho gayi hai. Aaj se aap mere configured boss hain. Voice commands par aapki awaaz match karunga; voice matching perfect ya replay-proof nahi hai."
    except Exception as e:
        print(f"⚠️ Enrollment Error: {e}")
        return False, str(e)
    finally:
        if not was_paused:
            microphone_paused.clear()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

import queue
_speech_queue = queue.Queue(maxsize=12)
_speech_thread = None
_speech_start_lock = threading.Lock()

def _speech_worker():
    while True:
        text, engine = _speech_queue.get()
        try:
            _speak_now(text, engine)
        except Exception as exc:
            report_audio_error("Speech playback failed: " + type(exc).__name__)
        finally:
            _speech_queue.task_done()

def speak(text, engine=None):
    global _speech_thread
    update_voice_state(reply=str(text))
    with _speech_start_lock:
        if _speech_thread is None or not _speech_thread.is_alive():
            _speech_thread = threading.Thread(target=_speech_worker, name="JoJo speech", daemon=True)
            _speech_thread.start()
    try:
        _speech_queue.put_nowait((str(text), engine))
    except queue.Full:
        report_audio_error("Speech queue full; the full response is available in the desktop chat.")

def stop_speech():
    speech_cancel.set()
    while True:
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
        except queue.Empty:
            break
    sd.stop()
    try:
        winmm.mciSendStringW('stop jojo_audio', None, 0, None)
    except Exception:
        pass

def report_audio_error(message):
    with voice_state_lock:
        voice_state["audio_error"] = message

vad_listener = None

def get_vad_listener():
    global vad_listener
    if vad_listener is None:
        vad_listener = MicrophoneListener(sample_rate=AUDIO_SAMPLE_RATE, device=AUDIO_DEVICE_ID,
            suppressed=lambda: microphone_paused.is_set() or is_speaking or time.time() - last_speaking_time < .35,
            on_error=report_audio_error, language=read_preferences().get("speech_language", "hi-IN"))
    return vad_listener

def listen_command(duration=3.0):
    return get_vad_listener().listen(timeout=duration, max_speech_duration=30)

def dispatch_command(message, source="laptop"):
    from jojo_capabilities import enabled
    if not enabled('desktop') and source == 'laptop':
        # Keep chat available, but do not enter legacy direct OS action handlers.
        return ask_jojo_brain(message)
    global last_interaction_time
    checkpoint()
    from jojo_runtime import bind_device
    bind_device(source)
    from jojo_device_lock import desktop_command
    lock_reply=desktop_command(message,source)
    if lock_reply is not None:return lock_reply
    from jojo_learning import owner_command
    learning_reply=owner_command(message)
    if learning_reply is not None:return learning_reply
    from jojo_smart_home import smart_command
    smart_reply=smart_command(message)
    if smart_reply is not None:return smart_reply
    from jojo_security import security_command
    security_reply = security_command(message) if source == "laptop" else None
    if security_reply is not None:
        update_voice_state(reply=security_reply, status="listening" if is_active_session else "sleeping")
        return security_reply
    set_active_device(source)
    from jojo_policy import guard_desktop
    if source == "laptop":
        guard_desktop()
    update_voice_state(transcript=message, status="thinking")
    if not is_safe_command(message):
        set_outcome("needs_input")
        return SECURITY_REFUSAL_MSG
    # Compound commands must not stop at the first substring match.
    if is_explanation_request(message):
        reply = ask_jojo_brain(message)
    elif needs_planning(message):
        reply = jojo_agi.run_agent_cycle(message, context_notes="Target device: " + source)
    else:
        reply = handle_reminder_voice_command(message)
        if not reply:
            report_progress("Checking local command…")
            reply = execute_pc_tasks(message, source=source)
        if not reply:
            if is_agentic_request(message):
                reply = jojo_agi.run_agent_cycle(message, context_notes="Target device: " + source)
            else:
                reply = ask_jojo_brain(message)
    checkpoint()
    last_interaction_time = time.time()
    update_voice_state(reply=reply, status="listening" if is_active_session else "sleeping")
    return reply

from jojo_journal import record as record_conversation
from jojo_journal import recover_interrupted
recover_interrupted()
task_manager = TaskManager(dispatch_command, speaker=lambda text: speak(text), journal=record_conversation)


# ==========================================
# 🌐 7. LOCAL FASTAPI GATEWAY & WEB CONTROL CENTER
# ==========================================
app = FastAPI(title="JoJo AGI Control Center")

_allowed_origins = ["http://127.0.0.1:8000", "http://localhost:8000"]
_allowed_origins.extend(value.strip() for value in os.environ.get("JOJO_ALLOWED_ORIGINS", "").split(",") if value.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def restrict_browser_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in _allowed_origins:
        return JSONResponse({"detail": "This browser origin is not permitted to control JoJo."}, status_code=403)
    return await call_next(request)

class ReminderReq(BaseModel):
    message: str
    delay_seconds: int = 10

class QACacheReq(BaseModel):
    question: str
    answer: str

class SpeakReq(BaseModel):
    text: str
    voice_engine: str = None

class ChatReq(BaseModel):
    message: str
    source: str = "laptop"  # 'laptop' (default) or 'mobile'

class ConfigReq(BaseModel):
    boss_threshold: float = None
    session_timeout: int = None
    voice_engine: str = None
    piper_speed: float = None
    audio_device_id: int = None
    microphone_paused: bool = None
    speech_language: str = None

class NoteReq(BaseModel):
    text: str

class PCTaskReq(BaseModel):
    task: str

class MobileVisionReq(BaseModel):
    target: str
    image_base64: str = ""
    action: str = "tap"

class VerifyVoiceReq(BaseModel):
    audio_base64: str = None
    threshold: float = None

class VoiceCommandReq(BaseModel):
    command: str
    speaker: str = "boss"
    audio_base64: str = None
    source: str = "mobile"  # 'mobile' (PWA/phone) or 'laptop' (desktop)

class AGITaskReq(BaseModel):
    goal: str
    speak_update: bool = True

@app.get("/")
def serve_dashboard():
    web_file = os.path.join(os.path.dirname(__file__), "web", "index.html")
    if os.path.exists(web_file):
        return FileResponse(web_file)
    return HTMLResponse("<h1>JoJo AGI Core Running</h1>")

@app.get("/hud")
def serve_hud():
    hud_file = os.path.join(os.path.dirname(__file__), "web", "hud.html")
    if os.path.exists(hud_file):
        return FileResponse(hud_file)
    return HTMLResponse("<h1>JoJo HUD Not Found</h1>", status_code=404)

@app.get("/api/hud/minimize")
def api_minimize_hud():
    try:
        import jojo_overlay
        jojo_overlay.minimize_jojo_hud()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/hud/show")
def api_show_hud():
    try:
        import jojo_overlay
        jojo_overlay.show_jojo_hud()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/manifest.json")
def serve_manifest():
    manifest_file = os.path.join(os.path.dirname(__file__), "web", "manifest.json")
    if os.path.exists(manifest_file):
        return FileResponse(manifest_file, media_type="application/json")
    return HTMLResponse("{}", status_code=404)

@app.get("/head.glb")
def serve_head_glb():
    glb_file = os.path.join(os.path.dirname(__file__), "web", "head.glb")
    if os.path.exists(glb_file):
        return FileResponse(glb_file, media_type="model/gltf-binary")
    raise HTTPException(status_code=404, detail="3D Head Model Not Found")

@app.get("/three.min.js")
def serve_three_js():
    f = os.path.join(os.path.dirname(__file__), "web", "three.min.js")
    if os.path.exists(f):
        return FileResponse(f, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="three.min.js Not Found")

@app.get("/GLTFLoader.js")
def serve_gltf_loader():
    f = os.path.join(os.path.dirname(__file__), "web", "GLTFLoader.js")
    if os.path.exists(f):
        return FileResponse(f, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="GLTFLoader.js Not Found")

@app.get("/activation")
@app.get("/overlay")
def serve_activation_overlay():
    """🔮 Futuristic Glowing Orb & Glowing Edges Neural Activation VUI (Mobile & Laptop)"""
    f = os.path.join(os.path.dirname(__file__), "web", "activation.html")
    if os.path.exists(f):
        return FileResponse(f, media_type="text/html")
    raise HTTPException(status_code=404, detail="Activation overlay not found")

@app.get("/mobile_overlay")
def serve_mobile_overlay():
    """📱 Mobile JoJo native-style overlay PWA page"""
    f = os.path.join(os.path.dirname(__file__), "web", "activation.html")
    if not os.path.exists(f):
        f = os.path.join(os.path.dirname(__file__), "web", "mobile_overlay.html")
    if os.path.exists(f):
        return FileResponse(f, media_type="text/html")
    raise HTTPException(status_code=404, detail="Mobile overlay not found")

@app.get("/jojo_overlay_manifest.json")
def serve_overlay_manifest():
    """PWA Manifest for mobile overlay install"""
    f = os.path.join(os.path.dirname(__file__), "web", "jojo_overlay_manifest.json")
    if os.path.exists(f):
        return FileResponse(f, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/jojo_sw.js")
def serve_service_worker():
    """PWA Service Worker"""
    f = os.path.join(os.path.dirname(__file__), "web", "jojo_sw.js")
    if os.path.exists(f):
        return FileResponse(f, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")

@app.get("/icons/{filename}")
def serve_icon(filename: str):
    """PWA Icons"""
    f = os.path.join(os.path.dirname(__file__), "web", "icons", filename)
    if os.path.exists(f):
        return FileResponse(f, media_type="image/png")
    raise HTTPException(status_code=404, detail="Icon not found")

@app.get("/deploy")
def deploy_to_mobile(key: str):
    if key != "JOJO-SECURE-MASTER-KEY-99":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"status": "authorized", "ai_name": "JoJo"}

@app.get("/api/status")
def api_get_status():
    chat_count = 0
    cache_count = 0
    pending_reminders = 0
    notes_count = 0
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM chat_history")
        chat_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM qa_cache")
        cache_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reminders WHERE status = 'pending'")
        pending_reminders = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM notes")
        notes_count = c.fetchone()[0]
        conn.close()
    except Exception:
        pass

    return {
        "status": "online",
        "name": "JoJo",
        "local_ip": get_local_ip(),
        "is_active_session": is_active_session,
        "boss_profile_loaded": boss_profile is not None,
        "boss_threshold": BOSS_SIMILARITY_THRESHOLD,
        "session_timeout": SESSION_TIMEOUT,
        "current_voice_engine": "voice_2_madhur",
        "voice_name": "Voice 2: Microsoft Madhur Neural (Permanent)",
        "available_voices": [
            {"id": "voice_2_madhur", "name": "Voice 2: Microsoft Madhur Neural (Permanent)", "active": True}
        ],
        "chat_count": chat_count,
        "cache_count": cache_count,
        "pending_reminders": pending_reminders,
        "notes_count": notes_count,
        "firestore_connected": db is not None,
        "gemini_active_key_index": current_gemini_index + 1
    }

@app.get("/api/tts")
async def api_tts(text: str):
    clean = text.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Empty text")
    cached = get_cached_speech_path(clean)
    if cached:
        return FileResponse(cached, media_type="audio/mpeg")
    h = hashlib.md5(clean.encode("utf-8")).hexdigest()
    out = os.path.join(VOICE_CACHE_DIR, f"{h}.mp3")
    success = await synthesize_madhur_audio(clean, out)
    if success and os.path.exists(out):
        return FileResponse(out, media_type="audio/mpeg")
    raise HTTPException(status_code=500, detail="TTS synthesis failed")

@app.get("/api/reminders")
def api_list_reminders():
    results = []
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, message, trigger_time, status, created_at FROM reminders ORDER BY id DESC LIMIT 50")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            results.append({
                "id": r[0],
                "message": r[1],
                "trigger_time": r[2],
                "status": r[3],
                "created_at": r[4]
            })
    except Exception as e:
        print(f"⚠️ API Reminders Fetch Error: {e}")
    return results

@app.post("/api/reminders")
def api_create_reminder(req: ReminderReq):
    schedule_reminder(req.message, req.delay_seconds)
    return {"status": "success", "message": req.message, "delay_seconds": req.delay_seconds}

@app.delete("/api/reminders/{reminder_id}")
def api_delete_reminder(reminder_id: int):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT firestore_id FROM reminders WHERE id = ?", (reminder_id,))
        row = c.fetchone()
        c.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        conn.close()
        if db is not None and row and row[0]:
            try:
                db.collection("reminders").document(row[0]).delete()
            except Exception:
                pass
        return {"status": "deleted", "id": reminder_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/qa_cache")
def api_list_qa_cache():
    results = []
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, question, answer, hit_count, last_used FROM qa_cache ORDER BY hit_count DESC, id DESC")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            results.append({
                "id": r[0],
                "question": r[1],
                "answer": r[2],
                "hit_count": r[3],
                "last_used": r[4]
            })
    except Exception as e:
        print(f"⚠️ QA Cache Fetch Error: {e}")
    return results

@app.post("/api/qa_cache")
def api_save_qa_cache(req: QACacheReq):
    clean_q = clean_text_for_match(req.question)
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO qa_cache (question, answer, hit_count, last_used)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(question) DO UPDATE SET answer=excluded.answer, last_used=excluded.last_used
        ''', (clean_q, req.answer, time.time()))
        conn.commit()
        conn.close()
        return {"status": "saved", "question": clean_q, "answer": req.answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/qa_cache/{cache_id}")
def api_delete_qa_cache(cache_id: int):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM qa_cache WHERE id = ?", (cache_id,))
        conn.commit()
        conn.close()
        return {"status": "deleted", "id": cache_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/speak")
def api_speak_text(req: SpeakReq):
    threading.Thread(target=speak, args=(req.text, req.voice_engine), daemon=True).start()
    return {"status": "speaking", "text": req.text, "voice_engine": req.voice_engine or CURRENT_VOICE_ENGINE}

@app.post("/api/chat")
def api_chat_message(req: ChatReq, request: Request = None):
    msg = req.message.strip()
    # 🧠 Smart device context: req.source > User-Agent header > default laptop
    src = req.source or "laptop"
    if request:
        try:
            ua = request.headers.get("user-agent", "").lower()
            if any(k in ua for k in ["android", "iphone", "ipad", "mobile"]):
                src = "mobile"
            elif any(k in ua for k in ["windows", "macintosh", "linux", "x11"]) and req.source != "mobile":
                src = "laptop"
        except Exception:
            pass
    set_active_device(src)

    if not is_safe_command(msg):
        return {"reply": SECURITY_REFUSAL_MSG}

    return {"reply": task_manager.run_sync(msg, src)}

@app.get("/api/agi/status")
def api_agi_status():
    return jojo_agi.get_agent_state()

@app.post("/api/agi/execute")
def api_agi_execute(req: AGITaskReq):
    if not is_safe_command(req.goal):
        return {"ok": False, "reply": SECURITY_REFUSAL_MSG}
    ans = task_manager.run_sync(req.goal, "laptop")
    if req.speak_update:
        speak(ans)
    return {"ok": jojo_agi.get_agent_state().get("status") == "completed", "reply": ans, "state": jojo_agi.get_agent_state()}

@app.post("/api/pc_task")
def api_trigger_pc_task(req: PCTaskReq):
    result = task_manager.run_sync(req.task, get_active_device())
    if result:
        threading.Thread(target=speak, args=(result,), daemon=True).start()
        return {"status": "success", "message": result}
    return {"status": "unknown_task", "message": "टास्क समझ नहीं आया बॉस"}

@app.post("/api/mobile_vision_click")
def api_mobile_vision_click(req: MobileVisionReq):
    """
    Mobile AI Vision Click API:
    Allows phone (Termux/PWA/ADB) to send screen + target element.
    Gemini 3.6 Flash locates the element and returns exact coordinates or triggers touch!
    """
    if not req.target:
        raise HTTPException(status_code=400, detail="Target required")

    img_bytes = None
    width, height = 1080, 2400
    if req.image_base64:
        try:
            img_bytes = base64.b64decode(req.image_base64)
            im = Image.open(io.BytesIO(img_bytes))
            width, height = im.size
        except Exception:
            pass

    data = jmv.ai_locate_mobile_element(req.target, img_bytes=img_bytes, width=width, height=height)
    if data and data.get("found"):
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        elem = data.get("element_name", req.target)
        if jmv.is_adb_connected():
            jmv.mobile_tap(x, y)
        return {
            "status": "success",
            "found": True,
            "x": x,
            "y": y,
            "element_name": elem,
            "message": f"मोबाइल पर '{elem}' ({x}, {y}) पर टैप कर दिया!"
        }

    return {
        "status": "not_found",
        "found": False,
        "message": f"मोबाइल स्क्रीन पर '{req.target}' नहीं मिला"
    }

@app.get("/api/audio_devices")
def api_get_audio_devices():
    devices = []
    try:
        all_devs = sd.query_devices()
        for i, d in enumerate(all_devs):
            if d.get("max_input_channels", 0) > 0:
                devices.append({
                    "id": i,
                    "name": d.get("name", f"Device {i}"),
                    "channels": d.get("max_input_channels", 1),
                    "selected": i == AUDIO_DEVICE_ID
                })
    except Exception as e:
        print(f"⚠️ Audio query error: {e}")
    return devices

@app.post("/api/enroll_boss")
def api_enroll_boss():
    success, msg = enroll_boss_voice(duration=9)
    if success:
        threading.Thread(target=speak, args=(msg,), daemon=True).start()
        return {"status": "success", "message": msg}
    raise HTTPException(status_code=500, detail=msg)

@app.get("/api/chat_history")
def api_get_chat_history():
    history = []
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, timestamp, role, message FROM chat_history ORDER BY id DESC LIMIT 100")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            history.append({
                "id": r[0],
                "timestamp": r[1],
                "role": r[2],
                "message": r[3]
            })
    except Exception as e:
        print(f"⚠️ Chat history fetch error: {e}")
    return history

@app.delete("/api/chat_history")
def api_clear_chat_history():
    try:
        from jojo_journal import clear
        clear()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes")
def api_get_notes():
    notes = []
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, text, created_at FROM notes ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            notes.append({
                "id": r[0],
                "text": r[1],
                "created_at": r[2]
            })
    except Exception as e:
        print(f"⚠️ Notes fetch error: {e}")
    return notes

@app.post("/api/notes")
def api_create_note(req: NoteReq):
    n_id = add_local_note(req.text)
    return {"status": "created", "id": n_id, "text": req.text}

@app.delete("/api/notes/{note_id}")
def api_delete_note(note_id: int):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        conn.close()
        return {"status": "deleted", "id": note_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jojo_termux_setup.sh")
def serve_termux_setup():
    sh_file = os.path.join(os.path.dirname(__file__), "jojo_termux_setup.sh")
    if os.path.exists(sh_file):
        return FileResponse(sh_file, media_type="text/x-sh")
    return HTMLResponse("echo 'Termux setup script not found'", status_code=404)

@app.get("/jojo_mobile.py")
def serve_jojo_mobile():
    py_file = os.path.join(os.path.dirname(__file__), "jojo_mobile.py")
    if os.path.exists(py_file):
        return FileResponse(py_file, media_type="text/x-python")
    return HTMLResponse("# Mobile client script not found", status_code=404)

@app.get("/jojo_mobile_vision.py")
def serve_jojo_mobile_vision():
    py_file = os.path.join(os.path.dirname(__file__), "jojo_mobile_vision.py")
    if os.path.exists(py_file):
        return FileResponse(py_file, media_type="text/x-python")
    return HTMLResponse("# Mobile vision script not found", status_code=404)

@app.get("/jojo_config.py")
def serve_mobile_config_module():
    return FileResponse(str(ROOT / "jojo_config.py"), media_type="text/x-python")

@app.get("/jojo_policy.py")
def serve_mobile_policy_module():
    return FileResponse(str(ROOT / "jojo_policy.py"), media_type="text/x-python")

@app.get("/api/mobile_info")
def api_get_mobile_info():
    ip = get_local_ip()
    return {
        "local_ip": ip,
        "port": 8000,
        "web_url": f"http://{ip}:8000/",
        "termux_command": f"pkg install -y curl && curl -sL http://{ip}:8000/jojo_termux_setup.sh | bash"
    }

@app.post("/api/config")
def api_update_config(req: ConfigReq):
    global BOSS_SIMILARITY_THRESHOLD, SESSION_TIMEOUT, AUDIO_DEVICE_ID
    if req.boss_threshold is not None:
        BOSS_SIMILARITY_THRESHOLD = max(0.50, min(0.95, req.boss_threshold))
    if req.session_timeout is not None:
        SESSION_TIMEOUT = max(10, min(300, req.session_timeout))
    if req.audio_device_id is not None:
        AUDIO_DEVICE_ID = None if req.audio_device_id == -1 else req.audio_device_id
        if vad_listener is not None:
            vad_listener.close()
            vad_listener.device = AUDIO_DEVICE_ID
    if req.microphone_paused is not None:
        microphone_paused.set() if req.microphone_paused else microphone_paused.clear()
    if req.speech_language is not None:
        if req.speech_language not in ("hi-IN", "en-IN"):
            raise HTTPException(400, "Supported speech languages: hi-IN, en-IN")
        if vad_listener is not None:
            vad_listener.language = req.speech_language
    values = {"audio_device_id": AUDIO_DEVICE_ID, "session_timeout": SESSION_TIMEOUT, "boss_threshold": BOSS_SIMILARITY_THRESHOLD}
    if req.speech_language:
        values["speech_language"] = req.speech_language
    save_preferences(values)
    return {
        "status": "updated",
        "boss_threshold": BOSS_SIMILARITY_THRESHOLD,
        "session_timeout": SESSION_TIMEOUT,
        "voice_engine": "voice_2_madhur",
        "audio_device_id": AUDIO_DEVICE_ID
    }

@app.get("/api/voice_state")
def api_get_voice_state():
    with voice_state_lock:
        st = dict(voice_state)
        st["state"] = st.get("status", "sleeping")
        st["agi"] = jojo_agi.get_agent_state()
        st["transcript"] = st["last_transcript"]
        st["reply"] = st["last_reply"]
        st["microphone_paused"] = microphone_paused.is_set()
        st["owner_enrolled"] = boss_profile is not None
        from jojo_security import security_snapshot
        st["security"] = security_snapshot()
        st["voice_verification"] = "neural-speaker-embedding"
        st["owner_voice_error"] = voice_verifier.error
        st["audio_device_id"] = AUDIO_DEVICE_ID
        st["speech_language"] = vad_listener.language if vad_listener else read_preferences().get("speech_language", "hi-IN")
        st["task"] = task_manager.get(task_manager.active_id) if task_manager.active_id else None
        return st

@app.post("/api/verify_voice")
def api_verify_voice(req: VerifyVoiceReq):
    global BOSS_SIMILARITY_THRESHOLD
    if not req.audio_base64:
        return {"verified": False, "similarity": 0.0, "threshold": BOSS_SIMILARITY_THRESHOLD, "error": "No audio supplied"}
    samples, rate = audio_base64_to_mono_samples(req.audio_base64)
    if samples is not None and rate != AUDIO_SAMPLE_RATE:
        samples = signal.resample_poly(samples.astype(float), AUDIO_SAMPLE_RATE, rate).astype(np.int16)
    if samples is None or len(samples) == 0:
        return {"verified": False, "similarity": 0.0, "threshold": BOSS_SIMILARITY_THRESHOLD, "error": "Invalid audio"}
    res = verify_boss(samples, threshold=req.threshold)
    return {
        "verified": bool(res.is_match),
        "similarity": round(float(res.similarity), 3),
        "threshold": req.threshold or BOSS_SIMILARITY_THRESHOLD
    }

@app.post("/api/voice_command")
def api_process_voice_command(req: VoiceCommandReq, request: Request = None):
    global is_active_session, last_interaction_time
    cmd = req.command.strip()
    if not cmd or not req.audio_base64:
        return {"reply": "Owner voice audio is required. Enroll in desktop Settings first.", "allowed": False}
    if not is_active_session and strip_wake_word(cmd) == cmd:
        return {"reply": "Pehle JoJo boliye.", "allowed": False}

    # 🧠 Detect device source: req.source > request User-Agent > fallback
    dev_source = getattr(req, 'source', None) or "laptop"
    if request:
        try:
            ua = request.headers.get("user-agent", "").lower()
            if any(k in ua for k in ["android", "iphone", "ipad", "mobile"]):
                dev_source = "mobile"
            elif any(k in ua for k in ["windows", "macintosh", "linux", "x11"]) and req.source != "mobile":
                dev_source = "laptop"
        except Exception:
            pass
    set_active_device(dev_source)

    # Biometric voice verification if audio is provided
    if req.audio_base64:
        samples, rate = audio_base64_to_mono_samples(req.audio_base64)
        if samples is not None and rate != AUDIO_SAMPLE_RATE:
            samples = signal.resample_poly(samples.astype(float), AUDIO_SAMPLE_RATE, rate).astype(np.int16)
        if samples is None or len(samples) == 0:
            return {"reply": "Invalid audio; voice could not be verified.", "allowed": False}
        if samples is not None and len(samples) > 0:
            res = verify_boss(samples)
            if not res.is_match:
                refusal = "आप मेरे बॉस नहीं हो"
                update_voice_state(status="access_denied", speaker="stranger", transcript=cmd, reply=refusal, similarity=res.similarity, active=False)
                threading.Thread(target=speak, args=(refusal,), daemon=True).start()
                return {"reply": refusal, "allowed": False, "similarity": res.similarity}

    # Speaker is explicitly stranger
    if req.speaker == "stranger":
        refusal = "आप मेरे बॉस नहीं हो"
        update_voice_state(status="access_denied", speaker="stranger", transcript=cmd, reply=refusal, active=False)
        threading.Thread(target=speak, args=(refusal,), daemon=True).start()
        return {"reply": refusal, "allowed": False}

    # Boss verified
    is_active_session = True
    last_interaction_time = time.time()
    auto_trigger_desktop_hud()
    update_voice_state(status="authenticating", speaker="boss", transcript=cmd, active=True)

    # Wake word check: immediate greeting
    clean_cmd = cmd
    clean_cmd = strip_wake_word(clean_cmd)
    if not clean_cmd:
        greeting = "हाँ बॉस, बोलिए!"
        update_voice_state(status="boss_verified", speaker="boss", reply=greeting, active=True)
        threading.Thread(target=speak, args=(greeting,), daemon=True).start()
        return {"reply": greeting, "allowed": True}
    cmd = clean_cmd

    # 1. 🛡️ Strict Financial & OTP Security Barrier
    if not is_safe_command(cmd):
        refusal = SECURITY_REFUSAL_MSG
        update_voice_state(status="speaking", reply=refusal)
        threading.Thread(target=speak, args=(refusal,), daemon=True).start()
        return {"reply": refusal, "allowed": False}

    task = task_manager.submit(cmd, dev_source, True)
    return {"reply": "Command received; progress is available in the task status.", "allowed": True, "task_id": task["id"], "status": "queued"}

@app.post("/api/wake_session")
def api_wake_session(speaker: str = "boss"):
    # A caller-supplied speaker label is not authentication.
    return {"status": "denied", "reply": "Use /api/voice_command with owner audio and the JoJo wake word."}

@app.get("/reminder")
@app.post("/reminder")
def create_reminder_api(key: str, message: str, delay_seconds: int = 5):
    if key != "JOJO-SECURE-MASTER-KEY-99":
        raise HTTPException(status_code=401, detail="Unauthorized")
    schedule_reminder(message, delay_seconds)
    return {
        "status": "scheduled",
        "message": message,
        "delay_seconds": delay_seconds,
        "trigger_time": time.time() + delay_seconds
    }



# ==========================================
# 📢 8. PROACTIVE ASSISTANT DAEMON
# ==========================================
def schedule_reminder(message, delay_seconds):
    trigger_time = time.time() + max(1, delay_seconds)
    firestore_id = None

    if db is not None:
        try:
            doc_ref = db.collection("reminders").add({
                "message": message,
                "trigger_time": trigger_time,
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP,
                "source": "voice"
            })
            firestore_id = doc_ref[1].id
        except Exception as e:
            print(f"⚠️ Cloud Reminder Push Error: {e}")

    add_local_reminder(message, trigger_time, firestore_id=firestore_id)

def handle_reminder_voice_command(text_command):
    cmd = text_command.lower()
    reminder_keywords = ["याद दिला", "रिमाइंडर", "remind me", "reminder", "याद रखना", "अलर्ट", "yaad dila", "yaad rakhna", "alert"]
    if not any(k in cmd for k in reminder_keywords):
        return None

    delay = 10
    m_sec = re.search(r'(\d+)\s*(?:seconds?|sec|सेकंड|सेकेंड)', cmd)
    m_min = re.search(r'(\d+)\s*(?:minutes?|min|मिनट)', cmd)
    m_hr = re.search(r'(\d+)\s*(?:hours?|hr|घंटे|घंटा)', cmd)
    if m_sec:
        delay = int(m_sec.group(1))
    elif m_min:
        delay = int(m_min.group(1)) * 60
    elif m_hr:
        delay = int(m_hr.group(1)) * 3600

    clean_msg = text_command
    clean_msg = re.sub(r'(?:in\s+)?\d+\s*(?:seconds?|sec|minutes?|min|hours?|hr|सेकंड|सेकेंड|मिनट|घंटे|घंटा)(?:\s*(?:baad|बाद|ke baad|के बाद))?', '', clean_msg, flags=re.IGNORECASE)
    triggers = ['remind me to', 'remind me', 'set reminder to', 'set reminder', 'reminder', 'yaad dilana', 'yaad dilao', 'yaad dila dena', 'yaad dila do', 'yaad dila', 'याद दिलाना', 'याद दिलाओ', 'याद दिला देना', 'रिमाइंडर लगाओ', 'रिमाइंडर', 'याद रखना']
    for k in triggers:
        clean_msg = re.sub(re.escape(k), '', clean_msg, flags=re.IGNORECASE)

    clean_msg = re.sub(r'\b(?:ka|ke|ki|ko|lagao|karo|do|dena)\b', '', clean_msg, flags=re.IGNORECASE)
    clean_msg = re.sub(r'(?:का|के|की|को|लगाओ|करो|देना)\b', '', clean_msg)
    clean_msg = re.sub(r'\s+', ' ', clean_msg).strip(' ,.?!:;')
    if not clean_msg:
        clean_msg = "एक ज़रूरी काम"

    schedule_reminder(clean_msg, delay)

    if is_hindi_text(text_command):
        return f"डन बॉस! {delay} सेकंड में बता दूंगा।" if delay < 60 else f"हो गया बॉस, {delay // 60} मिनट में याद दिला दूंगा।"
    else:
        return f"Done Boss! Reminding you in {delay} seconds." if delay < 60 else f"Got it Boss, reminding you in {delay // 60} minutes."

def run_proactive_daemon():
    print("📢 JoJo Proactive Assistant: Background Daemon Active!")
    while True:
        try:
            now = time.time()
            if db is not None:
                try:
                    docs = db.collection("reminders").where("status", "==", "pending").stream()
                    for doc in docs:
                        data = doc.to_dict()
                        doc_id = doc.id
                        trigger_ts = data.get("trigger_time")
                        msg = data.get("message", "एक ज़रूरी काम")
                        if trigger_ts is not None:
                            sync_cloud_reminder_to_local(doc_id, msg, trigger_ts)
                except Exception:
                    pass

            due_reminders = get_due_local_reminders(now)
            for r_id, f_id, msg, trigger_time in due_reminders:
                clean_m = msg.strip()
                if is_hindi_text(clean_m):
                    if any(k in clean_m for k in ["टाइम", "समय", "time"]):
                        alert_text = f"बॉस, {clean_m}!"
                    elif clean_m.endswith("का") or clean_m.endswith("की") or clean_m.endswith("के"):
                        alert_text = f"बॉस, {clean_m} टाइम हो गया!"
                    else:
                        alert_text = f"बॉस, {clean_m} का टाइम हो गया!"
                else:
                    if "time" in clean_m.lower():
                        alert_text = f"Boss, {clean_m}!"
                    else:
                        alert_text = f"Boss, time for {clean_m}!"

                speak(alert_text)
                mark_local_reminder_completed(r_id)

                if db is not None and f_id:
                    try:
                        db.collection("reminders").document(f_id).update({
                            "status": "completed",
                            "spoken_at": firestore.SERVER_TIMESTAMP
                        })
                    except Exception:
                        pass
                elif db is not None and not f_id:
                    try:
                        db.collection("reminders").add({
                            "message": msg,
                            "trigger_time": trigger_time,
                            "status": "completed",
                            "spoken_at": firestore.SERVER_TIMESTAMP,
                            "source": "local_scheduler"
                        })
                    except Exception:
                        pass

        except Exception as e:
            print(f"⚠️ Proactive Daemon Exception: {e}")

        time.sleep(3)



# ==========================================
# ☁️ 8. CLOUD REMOTE RELAY LISTENER (CROSS-NETWORK SYNC)
# ==========================================
def run_cloud_remote_listener():
    if db is None:
        return
    print("☁️ JoJo Cloud Relay: Cross-Network remote command listener active!")
    while True:
        try:
            docs = db.collection("jojo_remote_commands").where("status", "==", "pending").stream()
            for doc in docs:
                data = doc.to_dict()
                doc_id = doc.id
                cmd = data.get("command", "").strip()
                speaker = data.get("speaker", "boss")
                if not cmd:
                    continue
                # Claim before execution so a failed response upload cannot replay OS actions.
                db.collection("jojo_remote_commands").document(doc_id).update({"status": "processing"})
                print(f"☁️ [Cloud Remote Command]: '{cmd}' (Speaker: {speaker})")

                if not is_safe_command(cmd):
                    reply = SECURITY_REFUSAL_MSG
                elif speaker != "boss":
                    reply = "आप मेरे बॉस नहीं हो"
                else:
                    reply = task_manager.run_sync(cmd, "mobile")

                db.collection("jojo_remote_commands").document(doc_id).update({
                    "status": "completed",
                    "reply": reply,
                    "responded_at": firestore.SERVER_TIMESTAMP
                })
                print(f"☁️ [Cloud Response]: '{reply[:50]}...'")
        except Exception as e:
            pass
        time.sleep(2)



# ==========================================
# 🚀 9. CONTINUOUS REAL-TIME CONVERSATION LOOP
# ==========================================
WAKE_WORDS = [
    "jojo", "jo jo", "hello jojo", "hey jojo", "hi jojo",
    "sun jojo", "सुन जोजो", "जोजो", "जो जो", "जो-जो", "ok jojo", "okay jojo"
]
SLEEP_WORDS = ["sleep", "stop", "chup", "chup ho jao", "bye", "alvida", "शांत", "रुक जाओ", "सो जाओ"]

def strip_wake_word(text):
    pattern = r"^(?:" + "|".join(re.escape(w) for w in sorted(WAKE_WORDS, key=len, reverse=True)) + r")(?:[\s,!।:-]+|$)"
    return re.sub(pattern, "", text.strip(), count=1, flags=re.IGNORECASE).strip()

class DesktopTaskReq(BaseModel):
    message: str
    source: str = "laptop"
    speak: bool = True

@app.get("/api/health")
def api_health():
    return {"service": "jojo", "version": 2, "model": MODEL, "api_configured": bool(GEMINI_KEYS)}

@app.get("/api/memory/history")
def api_memory_history():
    from jojo_journal import history
    return history()

@app.get('/api/memory/sync')
def api_memory_sync_status():
    from jojo_cloud_memory import status
    return status()

@app.get('/api/skills')
def api_skills():
    from jojo_capabilities import catalog, tool_catalog
    return {'skills':catalog(),'tools':tool_catalog(),'plugins':[{'name':'Generated executable plugins / arbitrary shell, HTTP, SQL and Git execution','enabled':False,'locked':True,'reason':'Disabled to preserve app/payment restrictions.'}]}

@app.post('/api/skills')
def api_set_skills(values: dict):
    from jojo_capabilities import update
    try:update(values)
    except ValueError as exc:raise HTTPException(400,str(exc))
    return api_skills()

@app.get("/api/security/status")
def api_security_status():
    from jojo_security import security_snapshot
    return security_snapshot()

@app.post("/api/security/quick_scan")
def api_security_quick_scan():
    from jojo_security import start_defender_scan
    return start_defender_scan()

@app.post("/api/tasks")
def api_submit_task(req: DesktopTaskReq):
    if is_stop_command(req.message):
        stop_speech()
        task = task_manager.cancel_task()
        return {"status": "cancel_requested", "task": task}
    try:
        return task_manager.submit(req.message, req.source, req.speak)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except queue.Full:
        raise HTTPException(429, "Task queue is full. Wait for a result before retrying.")

@app.get("/api/tasks/{task_id}")
def api_task_status(task_id: str):
    result = task_manager.get(task_id)
    if not result:
        raise HTTPException(404, "Task not found")
    return result

@app.post("/api/tasks/{task_id}/cancel")
def api_cancel_task(task_id: str):
    stop_speech()
    result = task_manager.cancel_task(None if task_id == "active" else task_id)
    return result or {"status": "idle", "reply": "No active task."}

@app.post("/api/shutdown")
def api_shutdown():
    shutdown_requested.set()
    microphone_paused.set()
    task_manager.stop_all()
    stop_speech()
    if vad_listener is not None:
        vad_listener.close()
    return {"status": "shutting_down"}

def start_services():
    from jojo_cloud_memory import start as start_memory_sync
    start_memory_sync(db,shutdown_requested)
    port = int(os.environ.get("JOJO_PORT", "8000"))
    server = uvicorn.Server(uvicorn.Config(app, host=os.environ.get("JOJO_HOST", "127.0.0.1"), port=port, log_level="warning"))
    api_thread = threading.Thread(target=server.run, name="JoJo API", daemon=True)
    api_thread.start()
    deadline = time.monotonic() + 12
    while not server.started:
        if not api_thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError(f"JoJo API did not start. Check whether port {port} is already in use.")
        time.sleep(.05)
    threading.Thread(target=run_proactive_daemon, name="JoJo reminders", daemon=True).start()
    threading.Thread(target=run_cloud_remote_listener, name="JoJo cloud", daemon=True).start()
    from jojo_security import start_security_monitor
    start_security_monitor(shutdown_requested)
    from jojo_usb import start as start_usb_reconnect
    start_usb_reconnect(shutdown_requested)
    return server, api_thread

def run_voice_loop():
    global is_active_session, last_interaction_time
    while not shutdown_requested.is_set():
        try:
            if microphone_paused.is_set():
                time.sleep(.15)
                continue
            text, mono_audio = listen_command(duration=3.0)
            if not text:
                if is_active_session and not task_manager.active_id and time.time() - last_interaction_time > SESSION_TIMEOUT:
                    is_active_session = False
                    update_voice_state(status="sleeping", active=False)
                continue
            update_voice_state(transcript=text)
            clean = strip_wake_word(text)
            wake_detected = clean != text.strip()
            if is_stop_command(clean):
                # Stop is deliberately available without speaker authentication.
                task_manager.cancel_task()
                stop_speech()
                continue
            if clean.casefold().strip(" .!।") in SLEEP_WORDS:
                is_active_session = False
                update_voice_state(status="sleeping", active=False)
                continue
            if not is_active_session and not wake_detected:
                continue
            res = verify_boss(mono_audio, threshold=BOSS_SIMILARITY_THRESHOLD)
            update_voice_state(similarity=res.similarity)
            if not res.is_match:
                is_active_session = False
                refusal = "आप मेरे बॉस नहीं हो" if boss_profile is not None else "Pehle desktop Settings mein apni voice enroll kijiye."
                update_voice_state(status="access_denied", speaker="stranger", reply=refusal, active=False)
                if wake_detected:
                    speak(refusal)
                continue
            is_active_session = True
            last_interaction_time = time.time()
            update_voice_state(status="listening", speaker="boss", active=True)
            if not clean:
                speak("हाँ बॉस, बोलिए!")
                continue
            task_manager.submit(clean, "laptop", True)
        except queue.Full:
            report_audio_error("Task queue full. Let the current task finish, or say stop.")
        except Exception as exc:
            report_audio_error("Voice loop recovered from " + type(exc).__name__ + ". Text input is available.")
            time.sleep(.5)

from jojo_android import register as register_android
register_android(app, sys.modules[__name__])

if __name__ == "__main__":
    server, api_thread = start_services()
    auto_trigger_desktop_hud()
    try:
        if "--no-voice" in sys.argv:
            shutdown_requested.wait()
        else:
            run_voice_loop()
    finally:
        task_manager.stop_all()
        if vad_listener is not None:
            vad_listener.close()
        server.should_exit = True
        api_thread.join(timeout=3)
