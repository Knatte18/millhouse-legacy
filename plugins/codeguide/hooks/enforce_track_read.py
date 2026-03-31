"""
PreToolUse hook for the Read tool: sets overview_read=True in session state
when a _codeguide/ file is accessed.
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _resolve import routing_root

data = json.load(sys.stdin)
session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")
filepath = data.get("tool_input", {}).get("file_path", "")

if "_codeguide" not in filepath.replace("\\", "/"):
    sys.exit(0)

sessions_dir = routing_root() / "runtime" / "sessions"
state_path = sessions_dir / f"{session_id}-state.json"

if state_path.exists():
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["overview_read"] = True
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

sys.exit(0)
