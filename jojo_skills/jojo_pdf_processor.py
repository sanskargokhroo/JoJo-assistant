"""
📦 JoJo Skill: PDF Processor
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
"""
import os
import sys
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_tools import pdf_extract_and_summarize

def read_pdf_file(file_path: str, max_chars: int = 15000) -> str:
    """Extracts and reads text from any PDF document.
    Args:
        file_path: Path to the PDF file.
        max_chars: Maximum characters to extract (default: 15,000).
    """
    return pdf_extract_and_summarize(file_path, max_chars)
