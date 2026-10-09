"""
📦 JoJo Skill: API Client
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
"""
import os
import sys
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_tools import http_request_tool

def call_rest_api(url: str, method: str = "GET", data: str = "") -> str:
    """Sends an HTTP GET or POST request to any REST API endpoint or webhook.
    Args:
        url: Full URL to call.
        method: HTTP Method ('GET', 'POST', 'PUT', 'DELETE').
        data: Optional body data or JSON string for POST/PUT.
    """
    return http_request_tool(url, method=method, data=data)
