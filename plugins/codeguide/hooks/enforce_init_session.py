"""
UserPromptSubmit hook: creates a fresh turn-scoped session state file.

Runs on every user message. Always overwrites — state is turn-scoped only.
Captures the user prompt so violations can be logged with context.
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _resolve import routing_root

data = json.load(sys.stdin)
session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")
prompt_text = data.get("prompt", "")[:500]  # cap at 500 chars

sessions_dir = routing_root() / "runtime" / "sessions"
sessions_dir.mkdir(parents=True, exist_ok=True)

state = {
    "session_id": session_id,
    "prompt": prompt_text,
    "overview_read": False,
    "search_count": 0,
    "subagents_spawned": 0,
    "subagents_injected": 0,
}

state_path = sessions_dir / f"{session_id}-state.json"
state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
