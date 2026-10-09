"""
🧰 JoJo AGI: JoJo Native Tool Suite
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
- Git Operations (status, diff, log, commit, add, branch)
- PDF Text Extraction & Summarization
- Zero-Key Live Weather (via Open-Meteo & wttr.in)
- Full REST HTTP Client (GET, POST, PUT, DELETE)
- SQLite Database Inspector & Query Runner
- Smart File Deduplication & Directory Organizer
"""

import os
import sys
import shutil
import subprocess
import json
import hashlib
import sqlite3
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ==========================================
# 🌿 1. GIT OPERATIONS TOOL
# ==========================================

def git_operations(action: str, repo_path: str = ".", args: str = "") -> str:
    """
    Performs version control operations on any local Git repository.
    Args:
        action: One of 'status', 'diff', 'log', 'branch', 'add', 'commit', 'checkout'.
        repo_path: Directory of the git repo (default is workspace root '.').
        args: Extra arguments (e.g. commit message, file paths, branch name).
    """
    if shutil.which("git") is None:
        return "⚠️ Git executable not found on PATH."

    target_dir = os.path.abspath(os.path.join(WORKSPACE_ROOT, repo_path))
    if not os.path.isdir(target_dir):
        return f"⚠️ Directory does not exist: {target_dir}"

    act = action.lower().strip()
    cmd = ["git", "-C", target_dir]

    if act == "status":
        cmd.extend(["status", "--short"])
    elif act == "diff":
        cmd.extend(["diff"])
        if args:
            cmd.extend(args.split())
    elif act == "log":
        n = "5"
        if args and args.isdigit():
            n = args
        cmd.extend(["log", f"-n{n}", "--oneline", "--decorate"])
    elif act == "branch":
        cmd.extend(["branch", "-a"])
    elif act == "add":
        files = args.split() if args else ["."]
        cmd.extend(["add"] + files)
    elif act == "commit":
        msg = args if args else "Automated update via JoJo AGI"
        cmd.extend(["commit", "-m", msg])
    elif act == "checkout":
        if not args:
            return "⚠️ Please specify a branch or commit to checkout."
        cmd.extend(["checkout", args.strip()])
    else:
        return f"⚠️ Unsupported git action: '{action}'. Choose from status, diff, log, branch, add, commit, checkout."

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = res.stdout.strip()
        if res.stderr:
            output += ("\n" if output else "") + res.stderr.strip()
        if not output:
            output = f"Git {action} completed with no output (exit code: {res.returncode})."
        return output[:4000]
    except Exception as e:
        return f"⚠️ Git error: {str(e)}"


# ==========================================
# 📄 2. PDF EXTRACTION & PROCESSING TOOL
# ==========================================

def pdf_extract_and_summarize(file_path: str, max_chars: int = 15000) -> str:
    """
    Extracts text content and metadata from a local PDF file.
    Args:
        file_path: Path to the PDF document.
        max_chars: Maximum characters of text to return (default: 15,000).
    """
    target = os.path.abspath(os.path.join(WORKSPACE_ROOT, file_path)) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(target):
        return f"⚠️ File not found: {target}"
    if not target.lower().endswith(".pdf"):
        return f"⚠️ Not a PDF file: {target}"

    text_pages = []

    # Attempt 1: pdfplumber if available
    try:
        import pdfplumber
        with pdfplumber.open(target) as pdf:
            total_pages = len(pdf.pages)
            for idx, p in enumerate(pdf.pages):
                txt = p.extract_text()
                if txt:
                    text_pages.append(f"--- Page {idx+1}/{total_pages} ---\n{txt}")
    except ImportError:
        # Attempt 2: pypdf / PyPDF2
        try:
            from pypdf import PdfReader
            reader = PdfReader(target)
            total_pages = len(reader.pages)
            for idx, p in enumerate(reader.pages):
                txt = p.extract_text()
                if txt:
                    text_pages.append(f"--- Page {idx+1}/{total_pages} ---\n{txt}")
        except ImportError:
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(target)
                total_pages = len(reader.pages)
                for idx, p in enumerate(reader.pages):
                    txt = p.extract_text()
                    if txt:
                        text_pages.append(f"--- Page {idx+1}/{total_pages} ---\n{txt}")
            except Exception as e:
                return f"⚠️ No PDF library installed (install pdfplumber or pypdf): {str(e)}"
    except Exception as e:
        return f"⚠️ PDF parsing error: {str(e)}"

    if not text_pages:
        return "⚠️ PDF was loaded but contains no extractable text (it may be scanned/image-only)."

    full_text = "\n\n".join(text_pages)
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + f"\n\n... (truncated {len(full_text) - max_chars} characters)"

    return f"📄 PDF Extracted Content ({len(text_pages)} pages extracted):\n\n{full_text}"


# ==========================================
# ☀️ 3. ZERO-KEY LIVE WEATHER TOOL
# ==========================================

def get_live_weather(location: str = "auto") -> str:
    """
    Fetches real-time weather information and short-term forecast for any city or location.
    Works 100% free with zero API key requirement via Open-Meteo & wttr.in.
    Args:
        location: City name (e.g. 'Mumbai', 'Delhi', 'London', 'New York') or 'auto' for current IP location.
    """
    loc_clean = location.strip()
    if not loc_clean or loc_clean.lower() == "auto":
        loc_clean = ""

    # Strategy 1: wttr.in format (rich, instant ASCII / structured)
    try:
        url = f"https://wttr.in/{urllib.parse.quote(loc_clean)}?format=j1" if loc_clean else "https://wttr.in/?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]
        city = area.get("areaName", [{}])[0].get("value", location)
        country = area.get("country", [{}])[0].get("value", "")
        
        temp_c = current.get("temp_C", "?")
        feels_c = current.get("FeelsLikeC", "?")
        desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
        humidity = current.get("humidity", "?")
        wind_kmph = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "")

        return (
            f"🌤️ Weather for {city}, {country}:\n"
            f"• Condition: {desc}\n"
            f"• Temperature: {temp_c}°C (Feels like {feels_c}°C)\n"
            f"• Humidity: {humidity}%\n"
            f"• Wind: {wind_kmph} km/h {wind_dir}\n"
        )
    except Exception:
        pass

    # Strategy 2: Fallback to plain text wttr.in
    try:
        url = f"https://wttr.in/{urllib.parse.quote(loc_clean)}?format=%l:+%c+%t+(feels+like+%f),+humidity:+%h,+wind:+%w"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return f"🌤️ Live Weather: {resp.read().decode('utf-8').strip()}"
    except Exception as e:
        return f"⚠️ Unable to fetch live weather: {str(e)}"


# ==========================================
# 🌐 4. HTTP REST CLIENT TOOL
# ==========================================

def http_request_tool(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[str] = None
) -> str:
    """
    Sends an HTTP request (GET, POST, PUT, DELETE) to any REST API endpoint or webhook.
    Args:
        url: Full destination URL.
        method: HTTP method (GET, POST, PUT, DELETE). Default is 'GET'.
        headers: Optional dictionary of HTTP headers.
        data: Optional body string or JSON payload.
    """
    m = method.upper().strip()
    hdrs = headers or {}
    if "User-Agent" not in hdrs:
        hdrs["User-Agent"] = "JoJo-AGI/1.0 (Autonomous-Agent)"

    body_bytes = None
    if data:
        body_bytes = data.encode("utf-8")
        if "Content-Type" not in hdrs:
            hdrs["Content-Type"] = "application/json"

    try:
        req = urllib.request.Request(url, data=body_bytes, headers=hdrs, method=m)
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            return f"HTTP {status} OK\nResponse:\n{content[:4000]}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return f"⚠️ HTTP {e.code} Error: {e.reason}\n{err_body[:1000]}"
    except Exception as e:
        return f"⚠️ HTTP Request Failed: {str(e)}"


# ==========================================
# 🗄️ 5. SQLITE DATABASE TOOL
# ==========================================

def sqlite_query_tool(db_path: str, query: str) -> str:
    """
    Queries an SQLite database and returns results as formatted rows or executes updates.
    Args:
        db_path: Path to the SQLite .db file.
        query: SQL statement (e.g. 'SELECT name, sql FROM sqlite_master WHERE type="table"', 'SELECT * FROM users LIMIT 5').
    """
    target = os.path.abspath(os.path.join(WORKSPACE_ROOT, db_path)) if not os.path.isabs(db_path) else db_path
    if not os.path.exists(target):
        return f"⚠️ Database file not found: {target}"

    try:
        conn = sqlite3.connect(target)
        c = conn.cursor()
        c.execute(query)

        is_select = query.strip().upper().startswith("SELECT") or query.strip().upper().startswith("PRAGMA")
        if is_select:
            rows = c.fetchall()
            headers = [desc[0] for desc in c.description] if c.description else []
            conn.close()

            if not rows:
                return f"Query returned 0 rows. (Columns: {', '.join(headers)})"

            # Format as simple table
            header_str = " | ".join(headers)
            separator = "-+-".join(["-" * len(h) for h in headers])
            row_strs = [" | ".join([str(val) for val in r]) for r in rows[:50]]
            res = f"{header_str}\n{separator}\n" + "\n".join(row_strs)
            if len(rows) > 50:
                res += f"\n... ({len(rows) - 50} more rows truncated)"
            return res
        else:
            conn.commit()
            changes = conn.total_changes
            conn.close()
            return f"SQL executed successfully. Rows affected: {changes}"
    except Exception as e:
        return f"⚠️ SQLite Error: {str(e)}"


# ==========================================
# 🧹 6. FILE DEDUPLICATION & ORGANIZER TOOL
# ==========================================

def file_deduplicate_and_organize(
    directory_path: str,
    action: str = "find_duplicates"
) -> str:
    """
    Scans a directory to detect duplicate files by cryptographic SHA-256 hash or organize files by category.
    Args:
        directory_path: Directory to inspect.
        action: 'find_duplicates' or 'categorize_summary'.
    """
    target = os.path.abspath(os.path.join(WORKSPACE_ROOT, directory_path)) if not os.path.isabs(directory_path) else directory_path
    if not os.path.isdir(target):
        return f"⚠️ Directory not found: {target}"

    if action == "find_duplicates":
        hashes: Dict[str, List[str]] = {}
        file_count = 0

        for root, _, files in os.walk(target):
            for f in files:
                file_count += 1
                fp = os.path.join(root, f)
                try:
                    if os.path.getsize(fp) > 100 * 1024 * 1024:  # Skip >100MB
                        continue
                    hasher = hashlib.sha256()
                    with open(fp, "rb") as fh:
                        while chunk := fh.read(65536):
                            hasher.update(chunk)
                    h = hasher.hexdigest()
                    hashes.setdefault(h, []).append(fp)
                except Exception:
                    pass

        duplicates = {h: paths for h, paths in hashes.items() if len(paths) > 1}
        if not duplicates:
            return f"✅ No duplicate files found among {file_count} files in '{directory_path}'."

        res = [f"🔍 Found {len(duplicates)} sets of duplicate files:"]
        for idx, (h, paths) in enumerate(duplicates.items(), 1):
            res.append(f"\nDuplicate Set #{idx} (Hash: {h[:10]}...):")
            for p in paths:
                rel = os.path.relpath(p, target)
                res.append(f"  • {rel} ({os.path.getsize(p)} bytes)")
        return "\n".join(res)

    elif action == "categorize_summary":
        categories = {
            "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".rs", ".go", ".c", ".cpp"],
            "Documents": [".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".pptx"],
            "Images": [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"],
            "Media": [".mp3", ".wav", ".mp4", ".mov", ".mkv"],
            "Archives": [".zip", ".tar", ".gz", ".7z", ".rar"]
        }
        stats: Dict[str, int] = {k: 0 for k in categories}
        stats["Other"] = 0

        for root, _, files in os.walk(target):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                matched = False
                for cat, exts in categories.items():
                    if ext in exts:
                        stats[cat] += 1
                        matched = True
                        break
                if not matched:
                    stats["Other"] += 1

        summary = [f"📊 File Category Summary for '{directory_path}':"]
        for cat, cnt in stats.items():
            if cnt > 0:
                summary.append(f"• {cat}: {cnt} files")
        return "\n".join(summary)

    return f"⚠️ Unknown action '{action}'. Choose 'find_duplicates' or 'categorize_summary'."
