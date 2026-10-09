"""
📁 JoJo AGI: File System & Workspace Operations
Provides safe, comprehensive workspace file management:
- Read files (with line limits)
- Write & append files
- List directories with details
- Search files by name/glob
"""

import os
import glob
import fnmatch

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DESKTOP_PATH = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop")

def resolve_path(file_path: str) -> str:
    """Resolves relative or alias paths like 'Desktop' or 'c:/JoJo' safely."""
    p = file_path.strip().replace("\\", "/")
    if p.lower().startswith("desktop/"):
        return os.path.join(DESKTOP_PATH, p[8:])
    elif p.lower() == "desktop":
        return DESKTOP_PATH
    if not os.path.isabs(p):
        return os.path.abspath(os.path.join(WORKSPACE_ROOT, p))
    return os.path.abspath(p)

def read_file(file_path: str, max_lines: int = 500) -> str:
    """Reads and returns the contents of a local file."""
    abs_path = resolve_path(file_path)
    if not os.path.exists(abs_path):
        return f"❌ File not found: {abs_path}"
    if os.path.isdir(abs_path):
        return f"❌ Specified path is a directory, not a file: {abs_path}"

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
            content = "".join(lines)
            
        remaining = 0
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                total_lines = sum(1 for _ in f)
            if total_lines > max_lines:
                content += f"\n... [Truncated: Showing first {max_lines} of {total_lines} lines]"
        except Exception:
            pass

        return f"📄 File: {abs_path}\n\n{content}"
    except Exception as e:
        return f"⚠️ Error reading file {abs_path}: {str(e)}"

def write_file(file_path: str, content: str) -> str:
    """Writes content to a file, creating parent directories if necessary."""
    abs_path = resolve_path(file_path)
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(abs_path)
        return f"✅ File written successfully: {abs_path} ({size} bytes)"
    except Exception as e:
        return f"⚠️ Error writing file {abs_path}: {str(e)}"

def append_file(file_path: str, content: str) -> str:
    """Appends content to an existing file."""
    abs_path = resolve_path(file_path)
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(abs_path)
        return f"✅ Content appended successfully: {abs_path} (new size: {size} bytes)"
    except Exception as e:
        return f"⚠️ Error appending to file {abs_path}: {str(e)}"

def list_directory(dir_path: str = ".") -> str:
    """Lists files and folders inside the specified directory with file sizes."""
    abs_path = resolve_path(dir_path)
    if not os.path.exists(abs_path):
        return f"❌ Directory not found: {abs_path}"
    if not os.path.isdir(abs_path):
        return f"❌ Path is a file, not a directory: {abs_path}"

    try:
        entries = sorted(os.listdir(abs_path))
        lines = [f"📂 Directory: {abs_path} ({len(entries)} items)"]
        for entry in entries[:60]: # cap to 60 for clean token usage
            entry_path = os.path.join(abs_path, entry)
            if os.path.isdir(entry_path):
                lines.append(f"  📁 {entry}/")
            else:
                sz = os.path.getsize(entry_path)
                lines.append(f"  📄 {entry} ({sz} bytes)")
        if len(entries) > 60:
            lines.append(f"  ... and {len(entries) - 60} more items.")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Error listing directory {abs_path}: {str(e)}"

def search_files(pattern: str, dir_path: str = ".") -> str:
    """Searches for files matching a wildcard pattern (e.g., '*.py', '*test*') in a directory."""
    abs_path = resolve_path(dir_path)
    if not os.path.exists(abs_path):
        return f"❌ Directory not found: {abs_path}"

    matches = []
    try:
        for root, dirs, files in os.walk(abs_path):
            # Skip hidden / venv / pycache
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', 'venv', 'env')]
            for f in files:
                if fnmatch.fnmatch(f.lower(), pattern.lower()):
                    rel = os.path.relpath(os.path.join(root, f), abs_path)
                    matches.append(rel)
                if len(matches) >= 40:
                    break
            if len(matches) >= 40:
                break
        if matches:
            return f"🔍 Found {len(matches)} files matching '{pattern}' in {abs_path}:\n" + "\n".join(f"  - {m}" for m in matches)
        return f"No files matching '{pattern}' found in {abs_path}."
    except Exception as e:
        return f"⚠️ Search error: {str(e)}"
