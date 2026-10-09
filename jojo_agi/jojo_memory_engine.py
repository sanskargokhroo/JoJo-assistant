from jojo_config import api_keys, make_client, MODEL, DATA_DIR
"""
🧠 JoJo AGI: Hierarchical Cognitive Memory Engine
Combines:
1. Working Memory (Active goal scratchpad & sub-tasks)
2. Episodic Memory (Past task experiences, outcomes, and lessons)
3. Semantic Vector Memory (Embedding-based associative knowledge recall)
4. User Profile & Habits
"""

import sqlite3
import time
import os
import json
import numpy as np
from typing import List, Dict, Any, Optional
from google import genai

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_FILE = str(DATA_DIR / "jojo_memory.db")

GEMINI_KEYS = api_keys()
_emb_key_idx = 0

def get_genai_client():
    global _emb_key_idx
    return make_client(api_key=GEMINI_KEYS[_emb_key_idx])

# ==========================================
# 💾 DATABASE INITIALIZATION FOR AGI MEMORY
# ==========================================
def init_agi_memory_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Episodic Memory: Past tasks, plans, and lessons
    c.execute('''
        CREATE TABLE IF NOT EXISTS episodic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            goal TEXT,
            plan TEXT,
            tools_used TEXT,
            outcome TEXT,
            lessons_learned TEXT
        )
    ''')
    
    # 2. Semantic Vector Knowledge Base
    c.execute('''
        CREATE TABLE IF NOT EXISTS semantic_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            category TEXT,
            embedding BLOB,
            created_at REAL
        )
    ''')
    
    conn.commit()
    conn.close()

init_agi_memory_db()

# ==========================================
# 🔢 EMBEDDING & VECTOR RETRIEVAL (gemini-embedding-001)
# ==========================================
def compute_embedding(text: str) -> Optional[np.ndarray]:
    """Generates a normalized 3072-dimensional embedding vector for text."""
    global _emb_key_idx
    from jojo_config import PROVIDER
    if PROVIDER != 'gemini':
        return None
    for _ in range(len(GEMINI_KEYS)):
        try:
            client = get_genai_client()
            res = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text
            )
            vec = np.array(res.embeddings[0].values, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec
        except Exception as e:
            print(f"⚠️ Embedding API Key {_emb_key_idx} error: {e}")
            _emb_key_idx = (_emb_key_idx + 1) % max(1, len(GEMINI_KEYS))
    return None

def store_semantic_memory(content: str, category: str = "general") -> str:
    """Stores a fact or knowledge item with its semantic vector embedding."""
    vec = compute_embedding(content)
    if vec is None:
        return "⚠️ Failed to generate embedding for semantic memory."

    blob = vec.tobytes()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO semantic_knowledge (content, category, embedding, created_at) VALUES (?, ?, ?, ?)",
        (content, category, blob, time.time())
    )
    conn.commit()
    conn.close()
    return f"🧠 Successfully stored semantic memory in '{category}'."

def search_semantic_memory(query: str, top_k: int = 3, threshold: float = 0.45) -> List[Dict[str, Any]]:
    """Performs semantic similarity search across knowledge using vector embeddings."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, content, category, embedding FROM semantic_knowledge")
    rows = c.fetchall()
    conn.close()
    if not rows:
        return []
    q_vec = compute_embedding(query)
    if q_vec is None:
        return []

    results = []
    for r_id, content, cat, blob in rows:
        if not blob:
            continue
        mem_vec = np.frombuffer(blob, dtype=np.float32)
        if mem_vec.shape != q_vec.shape:
            continue
        sim = float(np.dot(q_vec, mem_vec))
        if sim >= threshold:
            results.append({
                "id": r_id,
                "content": content,
                "category": cat,
                "similarity": sim
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]

# ==========================================
# 📖 EPISODIC MEMORY (EXPERIENCES & LESSONS)
# ==========================================
def log_episode(goal: str, plan: str, tools_used: List[str], outcome: str, lessons: str = ""):
    """Logs a completed agent task episode to episodic memory."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO episodic_memory (timestamp, goal, plan, tools_used, outcome, lessons_learned)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (time.time(), goal, plan, json.dumps(tools_used), outcome, lessons))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Error logging episode: {e}")

def recall_relevant_episodes(query: str, limit: int = 2) -> str:
    """Finds past task episodes that might be relevant to the current goal."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Query recent episodes
        c.execute('''
            SELECT goal, outcome, lessons_learned FROM episodic_memory 
            ORDER BY id DESC LIMIT 15
        ''')
        episodes = c.fetchall()
        conn.close()

        if not episodes:
            return ""

        # Simple keyword matching for speed + relevance
        q_words = set(query.lower().split())
        matched = []
        for g, out, les in episodes:
            g_words = set(g.lower().split())
            if q_words.intersection(g_words):
                matched.append(f"• Goal: {g}\n  Outcome: {out[:120]}\n  Lesson: {les if les else 'Standard execution'}")

        if matched:
            return "\n[PAST EXPERIENCE / LESSONS]:\n" + "\n".join(matched[:limit])
    except Exception:
        pass
    return ""

# ==========================================
# 📝 WORKING MEMORY (ACTIVE SCRATCHPAD)
# ==========================================
class WorkingMemory:
    """Manages active short-term context, sub-tasks, and observations for a running agent task."""
    def __init__(self, goal: str):
        self.goal = goal
        self.start_time = time.time()
        self.subtasks: List[str] = []
        self.steps: List[Dict[str, Any]] = []
        self.variables: Dict[str, Any] = {}

    def add_step(self, thought: str, action: str, observation: str):
        self.steps.append({
            "step": len(self.steps) + 1,
            "thought": thought,
            "action": action,
            "observation": observation,
            "timestamp": time.time()
        })

    def get_summary(self) -> str:
        lines = [f"🎯 ACTIVE GOAL: {self.goal}"]
        if self.subtasks:
            lines.append("Subtasks: " + " -> ".join(self.subtasks))
        for s in self.steps[-3:]:  # Keep recent 3 steps in prompt buffer
            lines.append(f"Step {s['step']}: {s['thought']} | Action: {s['action']} | Result: {str(s['observation'])[:150]}")
        return "\n".join(lines)
