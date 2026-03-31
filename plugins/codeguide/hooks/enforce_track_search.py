"""
PreToolUse hook for Grep, Glob, and Bash tools: counts search calls and blocks
navigation violations (too many searches before reading _codeguide/).

On violation: logs the user prompt + search pattern to navigation-issues.md,
then exits with code 2 to block the tool call and force a corrective read.
"""

import json
import os
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _resolve import routing_root, load_config_flag

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# Determine whether this is a search operation and build a description
is_search = False
command_desc = ""

if tool_name == "Bash":
    command = tool_input.get("command", "")
    if any(x in command for x in ["grep", "rg ", "find "]):
        is_search = True
        command_desc = command[:200]
elif tool_name == "Grep":
    is_search = True
    command_desc = f"Grep: pattern={tool_input.get('pattern', '')} path={tool_input.get('path', '')}"
elif tool_name == "Glob":
    is_search = True
    command_desc = f"Glob: pattern={tool_input.get('pattern', '')} path={tool_input.get('path', '')}"

if not is_search:
    sys.exit(0)

# Don't count searches within _codeguide itself
if "_codeguide" in command_desc.replace("\\", "/"):
    sys.exit(0)

# Check flags — exit early if neither enforcement nor logging is active
enforcement = load_config_flag("enforcement")
violation_logging = load_config_flag("violation_logging")
if not enforcement and not violation_logging:
    sys.exit(0)

runtime_dir = routing_root() / "runtime"
sessions_dir = runtime_dir / "sessions"
issues_path = runtime_dir / "navigation-issues.md"

session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")
state_path = sessions_dir / f"{session_id}-state.json"

if not state_path.exists():
    sys.exit(0)

state = json.loads(state_path.read_text(encoding="utf-8"))
state["search_count"] = state.get("search_count", 0) + 1
state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

THRESHOLD = 3

if state["search_count"] > THRESHOLD and not state.get("overview_read", False):
    if violation_logging:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        prompt_snippet = state.get("prompt", "")[:200]
        entry = (
            f"\n## {timestamp} (session: {session_id})\n"
            f"- Prompt: `{prompt_snippet}`\n"
            f"- search_count: {state['search_count']}\n"
            f"- Tool: {tool_name}\n"
            f"- Pattern: `{command_desc}`\n"
        )
        with issues_path.open("a", encoding="utf-8") as f:
            f.write(entry)

    if enforcement:
        print(
            f"NAVIGATION VIOLATION: {state['search_count']} searches run without reading "
            f"_codeguide/. Stop. Read _codeguide/Overview.md now, then continue."
        )
        sys.exit(2)

sys.exit(0)
