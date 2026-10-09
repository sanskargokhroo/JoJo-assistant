"""
📦 JoJo Skill: Database Helper
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
"""
import os
import sys
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_tools import sqlite_query_tool

def query_sqlite_database(db_path: str, query: str) -> str:
    """Executes a SQL query or table inspection on a local SQLite database file.
    Args:
        db_path: Path to the SQLite .db file.
        query: SQL statement to execute.
    """
    return sqlite_query_tool(db_path, query)
