"""
📦 JoJo Skill: File Cleaner & Deduplicator
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
"""
import os
import sys
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_tools import file_deduplicate_and_organize

def scan_duplicate_files(directory_path: str = ".") -> str:
    """Scans a directory to detect duplicate files by SHA-256 hash.
    Args:
        directory_path: Directory path to scan (default is '.').
    """
    return file_deduplicate_and_organize(directory_path, action="find_duplicates")

def summarize_folder_categories(directory_path: str = ".") -> str:
    """Provides a categorical breakdown of all file types in a folder.
    Args:
        directory_path: Directory path to inspect (default is '.').
    """
    return file_deduplicate_and_organize(directory_path, action="categorize_summary")
