"""
🧠 JoJo AGI: Autonomous Cognitive Agent Architecture
"""

from jojo_agi.jojo_brain import run_agent_cycle, get_agent_state, update_agent_state
from jojo_agi.jojo_execution_engine import execute_powershell, execute_python_code, get_system_diagnostics
from jojo_agi.jojo_web_perception import web_search, read_webpage
from jojo_agi.jojo_file_ops import read_file, write_file, list_directory, search_files
from jojo_agi.jojo_memory_engine import store_semantic_memory, search_semantic_memory, log_episode
from jojo_agi.jojo_skill_synthesizer import synthesize_and_save_skill
from jojo_agi.jojo_tools_registry import get_all_tools
from jojo_agi.jojo_emotion_engine import (
    process_emotional_context,
    build_eq_context_string,
    JOJO_SOUL,
    detect_boss_mood,
    get_contextual_joke,
    get_self_reflection
)
from jojo_agi.jojo_ui_tars_agent import (
    UITarsAgent,
    UITarsActionParser,
    UI_TARS_SYSTEM_PROMPT
)
from jojo_agi.jojo_ui_tars_operator import (
    UITarsDesktopOperator,
    UITarsMobileOperator,
    UITarsUnifiedOperator
)
from jojo_agi.jojo_ui_tars_visualizer import (
    render_action_overlay
)
from jojo_agi.jojo_loop_guard import (
    LoopGuard,
    LoopVerdict
)
from jojo_agi.jojo_tools import (
    git_operations,
    pdf_extract_and_summarize,
    get_live_weather,
    http_request_tool,
    sqlite_query_tool,
    file_deduplicate_and_organize
)
from jojo_agi.jojo_research import (
    deep_research_topic
)
from jojo_agi.jojo_digest import (
    generate_daily_digest
)

__all__ = [
    "run_agent_cycle",
    "get_agent_state",
    "update_agent_state",
    "execute_powershell",
    "execute_python_code",
    "get_system_diagnostics",
    "web_search",
    "read_webpage",
    "read_file",
    "write_file",
    "list_directory",
    "search_files",
    "store_semantic_memory",
    "search_semantic_memory",
    "log_episode",
    "synthesize_and_save_skill",
    "get_all_tools",
    # Emotion & Behavior
    "process_emotional_context",
    "build_eq_context_string",
    "JOJO_SOUL",
    "detect_boss_mood",
    "get_contextual_joke",
    "get_self_reflection",
    # UI-TARS Integration
    "UITarsAgent",
    "UITarsActionParser",
    "UITarsDesktopOperator",
    "UITarsMobileOperator",
    "UITarsUnifiedOperator",
    "render_action_overlay",
    "UI_TARS_SYSTEM_PROMPT",
    # JoJo Integration
    "LoopGuard",
    "LoopVerdict",
    "git_operations",
    "pdf_extract_and_summarize",
    "get_live_weather",
    "http_request_tool",
    "sqlite_query_tool",
    "file_deduplicate_and_organize",
    "deep_research_topic",
    "generate_daily_digest"
]


