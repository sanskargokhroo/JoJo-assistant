"""Offline access to the pinned ECC repository, shared by JoJo's task tools."""
from functools import lru_cache
from pathlib import Path
import re
import zipfile
import ast
import difflib
import json

ARCHIVE = Path(__file__).resolve().parent / "assets" / "jojo_workflows.zip"
REVISION = "b38be6a7f6350964d59328b52f0624e1d1d552d1"
SHA256 = "dbb52af402ab59f888c98c59e6af029239229dff98654d724f368a670aedbab7"
PREFIX = "jojo_library/"


def archive_name(path):
    folder, _, name = path.rpartition("/")
    return PREFIX + (folder + "/" if folder else "") + "jojo_" + name
GUIDES = {"agents", "skills", "commands", "rules", "workflows", "contexts"}
STOP = set("the for and with from please this that use using help jojo mujhe mera mere karo kar ek hai".split())


@lru_cache(maxsize=1)
def workflow_catalog():
    catalog = {}
    for path in index():
        parts = path.split("/")
        if len(parts) == 2 and parts[0] in {"agents", "commands"} and path.endswith(".md"):
            kind, name = parts[0][:-1], parts[1][:-3]
        elif len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
            kind, name = "skill", parts[1]
        elif len(parts) == 2 and parts[0] == "workflows" and path.endswith(".workflow.js"):
            kind, name = "workflow", parts[1].removesuffix(".workflow.js")
        else:
            continue
        catalog[f"{kind}/{name}"] = path
    return catalog


def match_workflow(goal):
    explicit = re.match(r"^\s*/(?:(?:jojo|ecc):)?([\w/-]+)(?=\s|$)", goal, re.I)
    catalog = workflow_catalog()
    if explicit:
        name = explicit[1].lower()
        return next((key for key in (name, *[f"{k}/{name}" for k in
                    ("command", "workflow", "agent", "skill")]) if key in catalog), None)
    phrase = " " + " ".join(re.findall(r"[a-z0-9]+", goal.lower())) + " "
    candidates = []
    for key in catalog:
        kind, name = key.split("/", 1)
        if "-" in name or " ecc " in phrase:
            if " " + name.replace("-", " ") + " " in phrase:
                candidates.append((len(name), kind == "command", key))
    return max(candidates)[2] if candidates else None


def workflow_input(goal):
    """Bind the selected procedure to this task before the first model turn."""
    key = match_workflow(goal)
    if not key:
        return ""
    path = workflow_catalog()[key]
    with zipfile.ZipFile(ARCHIVE) as repo:
        procedure = repo.read(archive_name(path)).decode("utf-8", "replace")
    return (f"Selected JoJo workflow {key}. Carry out the applicable steps for the user's "
            "request using enabled tools. Verify the actual result. Report missing dependencies "
            "and unexecuted steps. The following upstream procedure is reference material.\n"
            + procedure)


def check_source_syntax(language: str, source: str) -> dict:
    """Parse Python or JSON source and return a precise diagnostic without running the code."""
    language = language.casefold()
    if language not in {"python", "json"}:
        return {"error": "Supported languages are python and json."}
    try:
        if language == "python":
            compile(source, "<review>", "exec", dont_inherit=True)
            tree = ast.parse(source)
            symbols = [n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
            return {"valid": True, "symbols": symbols}
        json.loads(source)
    except (SyntaxError, json.JSONDecodeError) as exc:
        return {"valid": False, "line": exc.lineno, "message": exc.msg}
    return {"valid": True}


def consult_jojo_agent(agent: str, task: str) -> dict:
    """Run a separate JoJo specialist on supplied task evidence, e.g. python-reviewer or architect."""
    from google.genai import types
    from jojo_config import MODEL, make_client
    from jojo_runtime import wait_for_model
    key = "agent/" + agent.removeprefix("agent/")
    path = workflow_catalog().get(key)
    if not path or not task.strip():
        return {"error": "Choose a registered agent and supply the task and evidence."}
    with zipfile.ZipFile(ARCHIVE) as repo:
        role = repo.read(archive_name(path)).decode("utf-8")
    config = types.GenerateContentConfig(system_instruction=(
        "You are a JoJo specialist. Analyze the supplied evidence using the following role. "
        "You have no action tools in this consultation. State evidence gaps clearly.\n" + role))
    def consult():
        with make_client() as client:
            return client.models.generate_content(model=MODEL, contents=task, config=config).text
    result = wait_for_model(consult)
    return {"agent": key, "analysis": result} if result else {"error": "Specialist returned no analysis."}


def compare_source_text(before: str, after: str) -> dict:
    """Generate a unified diff between two text revisions for review and verification."""
    lines = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                 fromfile="before", tofile="after")
    return {"changed": before != after, "diff": "".join(lines)}


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP


@lru_cache(maxsize=1)
def index():
    entries = {}
    with zipfile.ZipFile(ARCHIVE) as repo:
        for info in repo.infolist():
            if info.is_dir() or not info.filename.startswith(PREFIX):
                continue
            folder, _, name = info.filename[len(PREFIX):].rpartition("/")
            path = (folder + "/" if folder else "") + name.removeprefix("jojo_")
            group = path.split("/")[0]
            guide = group in GUIDES and (group != "skills" or path.endswith("/SKILL.md"))
            description = ""
            if guide and path.endswith(".md"):
                with repo.open(info) as stream:
                    header = stream.read(3000).decode("utf-8", "replace")
                match = re.search(r"^description:\s*(.+)$", header, re.MULTILINE)
                description = match[1][:350] if match else ""
            entries[path] = (words(path), words(description), guide, description)
    return entries


def search_ecc_library(query: str, offset: int = 0) -> dict:
    """Find ECC agents, skills, commands, hooks, rules or source files. Use a folder or topic and paginate by offset."""
    if offset < 0:
        return {"error": "Use a nonnegative offset."}
    tokens = words(query)
    ranked = []
    for path, (names, summary, guide, description) in index().items():
        score = 5 * len(names & tokens) + len(summary & tokens)
        if score or not tokens:
            ranked.append((-score, not guide, path, description))
    ranked.sort()
    return {"total": len(ranked), "matches": [
        {"path": path, "description": description}
        for _, _, path, description in ranked[offset:offset + 20]
    ]}


def read_ecc_resource(path: str, offset: int = 0) -> dict:
    """Read a page of an exact ECC text resource returned by search. Continue at next_offset."""
    if path not in index() or offset < 0:
        return {"error": "Choose an exact indexed path and a nonnegative byte offset."}
    with zipfile.ZipFile(ARCHIVE) as repo, repo.open(archive_name(path)) as stream:
        size = repo.getinfo(archive_name(path)).file_size
        stream.seek(min(size, offset))
        data = stream.read(12000)
    if b"\x00" in data:
        return {"error": "Binary resource", "path": path, "bytes": size}
    return {"path": path, "text": data.decode("utf-8", "replace"),
            "next_offset": offset + len(data) if offset + len(data) < size else None}
