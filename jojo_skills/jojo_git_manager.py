"""
📦 JoJo Skill: Git Manager
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
"""
import os
import sys
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_tools import git_operations

def manage_git_repo(action: str = "status", repo_path: str = ".", args: str = "") -> str:
    """Executes Git version control commands (status, diff, log, commit, add, branch, checkout).
    Args:
        action: Git action to perform ('status', 'diff', 'log', 'branch', 'add', 'commit', 'checkout').
        repo_path: Directory path of the repository.
        args: Extra arguments (e.g. commit message or branch name).
    """
    return git_operations(action=action, repo_path=repo_path, args=args)
