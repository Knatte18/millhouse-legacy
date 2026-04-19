---
name: mill-status-verify
plugin: mill
description: "Verify status.md against directory state for the active task."
---

# mill-status-verify

Verify the active task's `status.md` phase is consistent with directory state
(discussion.md, plan/, reviews/).

## When to use

- After a crash or interrupted run to confirm the task state is coherent.
- Before spawning a reviewer or proceeding to the next phase.
- Any time you suspect status.md is out of sync with the filesystem.

## Usage

```bash
PYTHONPATH=<repo>/plugins/mill/scripts python -m millpy.entrypoints.status_verify
```

Reads `.millhouse/wiki/active/<slug>/status.md` from the current worktree. Derives the
slug from the current git branch (stripping `repo.branch-prefix` if set).

## Exit codes

- `0` — consistent (or no active task found)
- `1` — at least one mismatch detected; mismatches printed to stdout

## What is checked

| Condition | Expected |
|-----------|----------|
| `plan/` directory present | `phase >= planned` |
| `phase = complete` | `plan/` and `discussion.md` present |
| Code-review files in `reviews/` | `phase >= reviewing` |

Unrecognized phase strings sort lower than all known phases and will trigger
mismatches for any condition that requires a minimum phase.
