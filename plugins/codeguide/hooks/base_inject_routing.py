"""
Routing instruction hook for UserPromptSubmit and SubagentStart.

Injects imperative instructions to read and follow _codeguide/Overview.md.
Does NOT inject the Overview content — Claude must actively Read the file,
which creates a deliberate step in its reasoning chain and triggers the
enforce_track_read.py enforcement hook.
"""

import json
import sys

hook_input = json.loads(sys.stdin.read())
event_name = hook_input["hook_event_name"]

context = (
    "STOP. Read _codeguide/Overview.md before doing anything else.\n"
    "It contains a routing table. Use it to find the right module doc.\n"
    "Docs are routing aids, NOT sources of truth — after routing, read the actual source files.\n"
    "Subagent prompts must include Overview. Read local-rules.md before editing docs.\n"
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": event_name,
        "additionalContext": context,
    }
}))
