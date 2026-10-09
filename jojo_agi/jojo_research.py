from jojo_config import api_keys, make_client, MODEL
"""
🔬 JoJo AGI: JoJo Deep Research Agent
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
- Multi-hop recursive research
- Automatic topic decomposition into investigative queries
- Parallel/sequential web & knowledge retrieval
- Cross-source synthesis, gap analysis, and citation formatting
- Outputs structured comprehensive reports with Executive Summary & Citations
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_web_perception import web_search, read_webpage
from google import genai
from google.genai import types

GEMINI_KEYS = api_keys()
_res_key_idx = 0

def get_gemini_client():
    global _res_key_idx
    key = GEMINI_KEYS[_res_key_idx]
    return make_client(api_key=key)

def rotate_key():
    global _res_key_idx
    _res_key_idx = (_res_key_idx + 1) % max(1, len(GEMINI_KEYS))


def deep_research_topic(
    topic: str,
    max_hops: int = 3,
    save_report: bool = True
) -> str:
    """
    Conducts a multi-hop deep research investigation on any topic using the JoJo research architecture.
    Decomposes the topic, gathers evidence from search queries, extracts key facts, and writes a cited narrative report.
    Args:
        topic: The subject, question, technology, or problem to research deeply.
        max_hops: Maximum investigative search iterations (default: 3).
        save_report: Whether to save the markdown report to scratch/research_reports/ (default: True).
    """
    print(f"🔬 Starting JoJo Deep Research on: '{topic}'...")

    # Step 1: Decompose Topic into Search Plan
    decomposition_prompt = (
        f"You are the JoJo Deep Research Planning Engine.\n"
        f"Topic to investigate: '{topic}'\n\n"
        f"Decompose this topic into 3 distinct, high-precision search queries that cover:\n"
        f"1. Core definitions, status, or architecture\n"
        f"2. Practical applications, latest developments, or benchmarks\n"
        f"3. Trade-offs, challenges, alternatives, or future outlook\n\n"
        f"Output ONLY a JSON array of 3 string search queries, e.g. [\"query 1\", \"query 2\", \"query 3\"]."
    )

    queries = [topic]
    for _ in range(len(GEMINI_KEYS)):
        try:
            client = get_gemini_client()
            resp = client.models.generate_content(
                model=MODEL,
                contents=decomposition_prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=300)
            )
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                queries = parsed[:max_hops]
                break
        except Exception:
            rotate_key()

    collected_evidence = []
    sources_cited = []

    # Step 2: Multi-Hop Search & Evidence Gathering
    for idx, q in enumerate(queries, 1):
        print(f"   [Hop {idx}/{len(queries)}] Searching: '{q}'...")
        search_res = web_search(q)
        collected_evidence.append(f"### Sub-Investigation #{idx}: {q}\n{search_res}")
        sources_cited.append(f"• Query: '{q}'")
        time.sleep(0.5)

    evidence_text = "\n\n".join(collected_evidence)

    # Step 3: Synthesis & Cited Report Generation
    synthesis_prompt = (
        f"You are JoJo's Deep Research Intelligence Engine, operating on the JoJo research paradigm.\n\n"
        f"Research Topic: {topic}\n\n"
        f"Collected Evidence:\n{evidence_text}\n\n"
        f"Write a thorough, highly authoritative Deep Research Report with the following structure:\n"
        f"# 📑 Deep Research Report: {topic}\n\n"
        f"## 1. Executive Summary\n(Crisp high-level synthesis of key findings)\n\n"
        f"## 2. In-Depth Technical Analysis & Insights\n(Structured breakdown with bullet points, mechanics, and concrete facts)\n\n"
        f"## 3. Real-World Practical Impact & Trade-offs\n(Key benefits, potential pitfalls, and comparison to alternatives)\n\n"
        f"## 4. Key Takeaways & Actionable Recommendations\n(Direct advice for Boss)\n\n"
        f"## 5. Evidence & Citations\n(List of search avenues used)\n\n"
        f"Tone: Intelligent, rigorous, articulate, and completely factual. Zero filler."
    )

    final_report = ""
    for _ in range(len(GEMINI_KEYS)):
        try:
            client = get_gemini_client()
            resp = client.models.generate_content(
                model=MODEL,
                contents=synthesis_prompt,
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=1800)
            )
            final_report = resp.text.strip()
            break
        except Exception as e:
            rotate_key()

    if not final_report:
        final_report = f"# Research Report: {topic}\n\nCollected Evidence:\n{evidence_text}"

    # Step 4: Persist to Workspace
    if save_report:
        out_dir = os.path.join(WORKSPACE_ROOT, "scratch", "research_reports")
        os.makedirs(out_dir, exist_ok=True)
        safe_title = "".join(c if c.isalnum() else "_" for c in topic[:30]).strip("_")
        out_path = os.path.join(out_dir, f"report_{safe_title}_{int(time.time())}.md")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(final_report)
            return f"{final_report}\n\n📁 Report saved to: {out_path}"
        except Exception:
            pass

    return final_report
