---
description: "Finalize, then implement all planned tasks"
model: opus
---

Finalize the current discussion, then implement all planned tasks committing after each.

- **Branch check first:** same as `finalize-do-commit` — if on `main`/`master` and `--onmain` is not in the argument, refuse, suggest a branch name, and stop. One branch for the entire batch.
- Finalize current discussion: create plan file, run `task_plan.py` to update backlog.
- Loop: run `do-commit` (find next planned task, implement, commit) until `task_get.py --include-planned` exits with code 1 (no planned tasks remain).
