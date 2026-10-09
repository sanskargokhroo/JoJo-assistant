"""
🧰 JoJo AGI: Universal Tools Registry
Aggregates all system, web, vision, memory, and code tools into clean callable functions
with clear type signatures and docstrings for Google GenAI Automatic Function Calling.
"""

from typing import List, Dict, Any, Callable
import os
import sys

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(WORKSPACE_ROOT)

from jojo_agi.jojo_execution_engine import (
    execute_powershell,
    execute_cmd,
    execute_python_code,
    get_system_diagnostics
)
from jojo_agi.jojo_web_perception import (
    web_search,
    read_webpage,
    wikipedia_summary
)
from jojo_agi.jojo_file_ops import (
    read_file,
    write_file,
    append_file,
    list_directory,
    search_files
)
from jojo_agi.jojo_vision_agent import (
    inspect_screen,
    click_screen_element,
    type_text,
    press_key
)
from jojo_agi.jojo_memory_engine import (
    store_semantic_memory,
    search_semantic_memory
)
from jojo_agi.jojo_skill_synthesizer import (
    synthesize_and_save_skill
)
from jojo_agi.jojo_ui_tars_agent import (
    UITarsAgent,
    UITarsActionParser
)
from jojo_agi.jojo_ui_tars_operator import (
    UITarsUnifiedOperator
)
from jojo_agi.jojo_ui_tars_visualizer import (
    render_action_overlay
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
from jojo_agi.jojo_loop_guard import (
    LoopGuard,
    LoopVerdict
)
# Generated executable skills are not imported in restricted-app mode.

# ==========================================
# 🎯 TOOL FUNCTIONS FOR GEMINI FUNCTION CALLING
# ==========================================

def run_powershell(command: str) -> str:
    """Executes a Windows PowerShell command to manage apps, files, networks, or system state.
    Args:
        command: The PowerShell command string to execute.
    """
    return execute_powershell(command)

def run_python_code(code: str) -> str:
    """Executes a snippet of Python code in the local environment and captures printed output or errors.
    Args:
        code: Complete Python code string to run.
    """
    return execute_python_code(code)

def search_the_web(query: str) -> str:
    """Performs a live internet search via DuckDuckGo and returns top titles, URLs, and snippets.
    Args:
        query: Search keywords or question.
    """
    return web_search(query)

def read_webpage_content(url: str) -> str:
    """Fetches and reads the full text content of any public webpage or documentation link.
    Args:
        url: The web URL to fetch.
    """
    return read_webpage(url)

def read_local_file(file_path: str) -> str:
    """Reads the contents of a local file in the workspace or desktop.
    Args:
        file_path: Path to the file (e.g., 'Desktop/notes.txt' or 'c:/JoJo/script.py').
    """
    return read_file(file_path)

def write_local_file(file_path: str, content: str) -> str:
    """Creates or overwrites a local file with the provided text content.
    Args:
        file_path: Path to the file (relative to workspace or absolute).
        content: The text/code to write into the file.
    """
    return write_file(file_path, content)

def append_to_file(file_path: str, content: str) -> str:
    """Appends text content to an existing local file.
    Args:
        file_path: Path to the file.
        content: Text to append.
    """
    return append_file(file_path, content)

def list_local_directory(dir_path: str = ".") -> str:
    """Lists files and folders inside a local directory.
    Args:
        dir_path: Directory path (e.g. '.' for workspace, 'Desktop' for Windows desktop).
    """
    return list_directory(dir_path)

def search_local_files(pattern: str, dir_path: str = ".") -> str:
    """Searches for files matching a pattern like '*.py' or '*test*' within a directory.
    Args:
        pattern: Wildcard search pattern.
        dir_path: Base directory to search from.
    """
    return search_files(pattern, dir_path)

def inspect_desktop_screen(query: str = "Describe what is on screen") -> str:
    """Captures a screenshot of the user's screen and visually analyzes it using Gemini Vision to inspect windows, code, or errors.
    Args:
        query: Specific question about what to look for on the screen.
    """
    return inspect_screen(query)

def click_ui_element(element_name: str) -> str:
    """Visually detects a UI button, menu item, or icon on screen and clicks it.
    Args:
        element_name: Name or description of the button/element to click (e.g., 'Close', 'Submit', 'Chrome icon').
    """
    return click_screen_element(element_name)

def type_into_active_window(text: str) -> str:
    """Types text directly into whatever window currently has focus on the PC.
    Args:
        text: Text to type.
    """
    return type_text(text)

def press_keyboard_key(key: str) -> str:
    """Presses a single key or shortcut (e.g., 'enter', 'esc', 'ctrl+c', 'alt+tab').
    Args:
        key: The key name or combination.
    """
    return press_key(key)

def get_pc_system_diagnostics() -> str:
    """Returns real-time computer diagnostics including CPU usage, RAM, disk space, and battery."""
    return get_system_diagnostics()

def search_semantic_memories(query: str) -> str:
    """Searches JoJo's long-term vector semantic knowledge base for relevant facts or past notes.
    Args:
        query: Concept or question to recall.
    """
    results = search_semantic_memory(query)
    if not results:
        return "No relevant memories found."
    return "\n".join([f"• [{r['category']}] {r['content']} (relevance: {r['similarity']:.2f})" for r in results])

def save_semantic_fact(content: str, category: str = "general") -> str:
    """Stores a fact or insight with vector embeddings in JoJo's permanent semantic memory.
    Args:
        content: Fact or information to remember.
        category: Category tag (e.g., 'boss_preferences', 'coding', 'project_notes').
    """
    return store_semantic_memory(content, category)

def create_new_persistent_skill(skill_name: str, python_code: str, test_code: str = "") -> str:
    """Synthesizes, tests, and permanently registers a new Python tool into JoJo's skill library for future reuse.
    Args:
        skill_name: Unique identifier for the skill (e.g. 'pdf_reader').
        python_code: Self-contained Python code implementing the functionality.
        test_code: Optional test snippet that runs without errors to verify the skill.
    """
    return synthesize_and_save_skill(skill_name, python_code, test_code)

def execute_ui_tars_action(action_str: str, platform: str = "auto") -> str:
    """Parses and executes a UI-TARS formatted GUI action on the Windows desktop or mobile device.
    Examples:
        click(start_box='[500, 300, 520, 320]')
        left_double(start_box='[120, 450, 150, 480]')
        right_single(start_box='[300, 200, 320, 220]')
        drag(start_box='[200, 300, 220, 320]', end_box='[500, 600, 520, 620]')
        type(content='Hello World\\n')
        hotkey(key='ctrl c')
        scroll(start_box='[500, 500, 500, 500]', direction='down')
        wait()
    Args:
        action_str: Exact UI-TARS action syntax string.
        platform: 'auto' uses this task's bound device. An explicit 'desktop' or 'mobile' must match it.
    """
    from jojo_runtime import target_platform
    platform = target_platform(platform)
    operator = UITarsUnifiedOperator(prefer_target=platform)
    w, h = (1920, 1080)
    try:
        if platform == "desktop":
            import pyautogui
            w, h = pyautogui.size()
    except Exception:
        pass

    actions = UITarsActionParser.parse_prediction(action_str, screen_width=w, screen_height=h)
    if not actions:
        return f"⚠️ Failed to parse UI-TARS action string: '{action_str}'"

    results = []
    for act in actions:
        from jojo_runtime import checkpoint
        checkpoint()
        res = operator.execute_action(act)
        results.append(f"[{res.get('status')}] {res.get('message')}")
    return " | ".join(results)

def run_gui_task_autonomous(task_description: str, max_steps: int = 20, platform: str = "auto") -> str:
    """Executes a multi-turn autonomous computer-use or mobile-use task using the UI-TARS visual loop.
    Captures live screenshots, uses visual grounding with reflection, parses actions, and executes them step-by-step.
    Args:
        task_description: Description of the goal to achieve (e.g. 'Open Notepad and type Boss Notes', 'Click on Settings').
        max_steps: Maximum autonomous steps before stopping (default: 8).
        platform: 'auto' uses this task's bound device; an explicit target must match it.
    """
    from jojo_runtime import target_platform
    platform = target_platform(platform)
    agent = UITarsAgent(target_platform=platform)
    res = agent.run_task(task_description, max_steps=max_steps)
    summary = f"🎯 UI-TARS Task Status: {res.get('status')}\nSummary: {res.get('message')}\nTotal Steps: {res.get('total_steps')}"
    if res.get("history"):
        summary += "\nSteps Executed:"
        for h in res["history"]:
            summary += f"\n  • Step {h['step']}: {h['action_str']} -> {h.get('exec_result', {}).get('message', 'ok')}"
    return summary

def render_ui_tars_overlay_tool(image_path: str, action_str: str) -> str:
    """Renders UI-TARS visualizer bounding boxes, target crosshairs, and action badges on a screenshot for visual inspection.
    Args:
        image_path: Path to the screenshot image file.
        action_str: The UI-TARS action string to visualize.
    """
    from PIL import Image
    if not os.path.exists(image_path):
        return f"⚠️ Image not found: {image_path}"
    try:
        img = Image.open(image_path)
        w, h = img.size
        actions = UITarsActionParser.parse_prediction(action_str, screen_width=w, screen_height=h)
        if not actions:
            return f"⚠️ No valid UI-TARS action found in: '{action_str}'"
        
        out_dir = os.path.join(WORKSPACE_ROOT, "scratch", "ui_tars_visuals")
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"overlay_{int(time.time())}.png")
        render_action_overlay(img, actions, output_path=out_file)
        return f"🎨 Visual overlay generated: {out_file}"
    except Exception as e:
        return f"⚠️ Visual overlay error: {str(e)}"

# ==========================================
# 🌌 JOJO TOOLS
# ==========================================

def research_deep_topic(topic: str, max_hops: int = 3) -> str:
    """Performs an exhaustive multi-hop deep research investigation on any topic using the JoJo research architecture.
    Decomposes the topic into queries, gathers multi-source web evidence, and writes a cited narrative report.
    Args:
        topic: The topic, question, or technology to research deeply.
        max_hops: Maximum investigative iterations (default: 3).
    """
    return deep_research_topic(topic, max_hops=max_hops)

def get_morning_briefing(city: str = "auto", focus_area: str = "general coding and system productivity") -> str:
    """Generates an JoJo Daily Morning Briefing synthesizing live weather, PC diagnostics, memory, and today's focus.
    Args:
        city: City for weather check (default: 'auto').
        focus_area: Main focus or goal for today.
    """
    return generate_daily_digest(city=city, user_focus=focus_area)

def git_vcs_control(action: str = "status", repo_path: str = ".", args: str = "") -> str:
    """Executes Git version control operations (status, diff, log, branch, add, commit, checkout).
    Args:
        action: Git action ('status', 'diff', 'log', 'branch', 'add', 'commit', 'checkout').
        repo_path: Directory path of the git repository.
        args: Extra arguments (e.g. commit message or branch name).
    """
    return git_operations(action=action, repo_path=repo_path, args=args)

def extract_pdf_text(file_path: str, max_chars: int = 15000) -> str:
    """Extracts and summarizes text from any local PDF document using JoJo PDF engine.
    Args:
        file_path: Relative or absolute path to the PDF file.
        max_chars: Maximum characters to extract (default: 15,000).
    """
    return pdf_extract_and_summarize(file_path, max_chars=max_chars)

def check_live_weather(location: str = "auto") -> str:
    """Fetches real-time live weather and forecast for any city or location without an API key.
    Args:
        location: City name (e.g. 'Mumbai', 'Delhi', 'London') or 'auto'.
    """
    return get_live_weather(location)

def send_http_request(url: str, method: str = "GET", data: str = "") -> str:
    """Sends an HTTP REST request (GET, POST, PUT, DELETE) to any web API or endpoint.
    Args:
        url: Full destination URL.
        method: HTTP method (default: 'GET').
        data: Optional body string or JSON string.
    """
    return http_request_tool(url=url, method=method, data=data)

def query_database_sqlite(db_path: str, query: str) -> str:
    """Queries an SQLite database and returns formatted rows or inspects database schema.
    Args:
        db_path: Path to the SQLite .db file.
        query: SQL statement to execute.
    """
    return sqlite_query_tool(db_path=db_path, query=query)

def deduplicate_and_organize_files(directory_path: str = ".", action: str = "find_duplicates") -> str:
    """Scans a directory to detect duplicate files by SHA-256 hash or summarizes file categories.
    Args:
        directory_path: Folder path to scan.
        action: 'find_duplicates' or 'categorize_summary'.
    """
    return file_deduplicate_and_organize(directory_path=directory_path, action=action)

def get_all_tools(include_disabled=False) -> List[Callable]:
    """Returns the list of all available tool callables for Gemini Function Calling."""
    from jojo_journal import remember_workflow
    from jojo_security import audit_device_security, inspect_link, inspect_app_file, wifi_security_guidance
    from jojo_smart_home import list_smart_devices, control_smart_device
    tools = [
        list_smart_devices,
        control_smart_device,
        audit_device_security,
        inspect_link,
        inspect_app_file,
        wifi_security_guidance,
        remember_workflow,
        run_powershell,
        run_python_code,
        search_the_web,
        read_webpage_content,
        read_local_file,
        write_local_file,
        append_to_file,
        list_local_directory,
        search_local_files,
        inspect_desktop_screen,
        click_ui_element,
        type_into_active_window,
        press_keyboard_key,
        get_pc_system_diagnostics,
        search_semantic_memories,
        save_semantic_fact,
        create_new_persistent_skill,
        # UI-TARS Integration Tools
        execute_ui_tars_action,
        run_gui_task_autonomous,
        render_ui_tars_overlay_tool,
        # JoJo Tools
        research_deep_topic,
        get_morning_briefing,
        git_vcs_control,
        extract_pdf_text,
        check_live_weather,
        send_http_request,
        query_database_sqlite,
        deduplicate_and_organize_files
    ]
    
    # Executable generated skills and arbitrary code bypass app restrictions.
    blocked = {'run_powershell', 'run_python_code', 'create_new_persistent_skill',
               'send_http_request', 'git_vcs_control', 'query_database_sqlite'}
    from jojo_capabilities import allowed_tool
    return [tool for tool in tools if tool.__name__ not in blocked and (include_disabled or allowed_tool(tool.__name__))]


