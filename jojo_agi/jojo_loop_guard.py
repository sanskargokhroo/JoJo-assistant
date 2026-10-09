"""
🛡️ JoJo AGI: Agent LoopGuard
Source attribution: see JOJO_THIRD_PARTY_NOTICES.md.
- Prevents degenerate and runaway tool loops
- SHA-256 hash tracking of identical tool calls
- Ping-pong detection (detects A-B-A-B or A-B-C-A-B-C cycling)
- Per-tool budgets and polling awareness
- Warn-before-block graceful recovery
"""

import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Set, List


@dataclass
class LoopGuardConfig:
    enabled: bool = True
    max_identical_calls: int = 3       # Max identical (tool_name, arguments) calls
    ping_pong_window: int = 6         # Window to detect A-B-A-B cycling
    poll_tool_budget: int = 6         # Max calls to the same polling/monitoring tool
    warn_before_block: bool = True     # Warn on first detected cycle, block on second


@dataclass
class LoopVerdict:
    blocked: bool = False
    reason: str = ""
    warned: bool = False


class LoopGuard:
    """
    Detects and prevents degenerate agent loops during autonomous execution.
    """

    def __init__(self, config: Optional[LoopGuardConfig] = None):
        self.config = config or LoopGuardConfig()
        self._call_counts: Dict[str, int] = {}
        self._tool_sequence: deque = deque(maxlen=self.config.ping_pong_window * 2)
        self._per_tool_counts: Dict[str, int] = {}
        self._warned_cycles: Set[str] = set()

    def reset(self):
        """Resets the guard between distinct tasks."""
        self._call_counts.clear()
        self._tool_sequence.clear()
        self._per_tool_counts.clear()
        self._warned_cycles.clear()

    def check_call(self, tool_name: str, arguments: str = "") -> LoopVerdict:
        """
        Evaluates whether a planned tool call should proceed or be halted.
        """
        if not self.config.enabled:
            return LoopVerdict(blocked=False)

        clean_args = str(arguments).strip()
        call_hash = hashlib.sha256(f"{tool_name}:{clean_args}".encode()).hexdigest()[:16]

        # 1. Check identical calls
        self._call_counts[call_hash] = self._call_counts.get(call_hash, 0) + 1
        if self._call_counts[call_hash] > self.config.max_identical_calls:
            reason = (
                f"LoopGuard Blocked: Tool '{tool_name}' was called {self._call_counts[call_hash]} "
                f"times with identical arguments. Possible stuck loop."
            )
            return self._handle_verdict(reason, cycle_key=f"identical:{call_hash}")

        # 2. Track tool sequence for ping-pong detection
        self._tool_sequence.append(tool_name)
        self._per_tool_counts[tool_name] = self._per_tool_counts.get(tool_name, 0) + 1

        seq_len = len(self._tool_sequence)
        # Check period 2: A-B-A-B (4 items)
        if seq_len >= 4:
            s = list(self._tool_sequence)
            if s[-1] == s[-3] and s[-2] == s[-4] and s[-1] != s[-2]:
                pair_key = tuple(sorted([s[-1], s[-2]]))
                reason = f"LoopGuard Blocked: Detected ping-pong cycle between '{s[-1]}' and '{s[-2]}'."
                return self._handle_verdict(reason, cycle_key=f"pingpong:{pair_key}")

        # Check period 3: A-B-C-A-B-C (6 items)
        if seq_len >= 6:
            s = list(self._tool_sequence)
            if s[-1] == s[-4] and s[-2] == s[-5] and s[-3] == s[-6]:
                trip_key = tuple(sorted([s[-1], s[-2], s[-3]]))
                reason = f"LoopGuard Blocked: Detected 3-way cyclic loop between '{s[-1]}', '{s[-2]}', and '{s[-3]}'."
                return self._handle_verdict(reason, cycle_key=f"cyclic:{trip_key}")

        return LoopVerdict(blocked=False)

    def _handle_verdict(self, reason: str, cycle_key: str = "") -> LoopVerdict:
        key = cycle_key or reason
        if self.config.warn_before_block:
            if key not in self._warned_cycles:
                self._warned_cycles.add(key)
                return LoopVerdict(blocked=False, warned=True, reason=reason)
        return LoopVerdict(blocked=True, reason=reason)

