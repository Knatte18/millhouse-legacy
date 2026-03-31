"""
SubagentStart hook: increments subagents_injected in session state.

Runs alongside the routing injection hook (base_inject_routing.py).
Together they form a parity check: subagents_spawned (from audit_track_task.py)
vs subagents_injected detects whether the injection hook ran for every subagent.
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _resolve import routing_root

data = json.load(sys.stdin)
session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")

sessions_dir = routing_root() / "runtime" / "sessions"
state_path = sessions_dir / f"{session_id}-state.json"

if state_path.exists():
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["subagents_injected"] = state.get("subagents_injected", 0) + 1
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

sys.exit(0)
