"""
Stop hook: logs subagent parity issues (if any) and deletes the turn-scoped
session state file.

State files are turn-scoped — created fresh each prompt, deleted here.
navigation-issues.md accumulates across the working session for /review-navigation.
"""

import json
import os
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _resolve import routing_root, load_config_flag

data = json.load(sys.stdin)
session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")

runtime_dir = routing_root() / "runtime"
sessions_dir = runtime_dir / "sessions"
issues_path = runtime_dir / "navigation-issues.md"
state_path = sessions_dir / f"{session_id}-state.json"

if not state_path.exists():
    exit(0)

state = json.loads(state_path.read_text(encoding="utf-8"))

spawned = state.get("subagents_spawned", 0)
injected = state.get("subagents_injected", 0)

if spawned > injected and load_config_flag("violation_logging"):
    runtime_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prompt_snippet = state.get("prompt", "")[:200]
    entry = (
        f"\n## {timestamp} — PARITY ISSUE (session: {session_id})\n"
        f"- Prompt: `{prompt_snippet}`\n"
        f"- subagents_spawned: {spawned}\n"
        f"- subagents_injected: {injected}\n"
        f"- {spawned - injected} subagent(s) may not have received the Overview injection\n"
    )
    with issues_path.open("a", encoding="utf-8") as f:
        f.write(entry)

state_path.unlink()
