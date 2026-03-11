---
description: "Implement all planned tasks, committing after each"
model: opus
---

Implement all planned tasks, committing after each.

- **Branch check first:** same as `do-commit` — if on `main`/`master`, prompt to create a new branch, wait for confirmation, create and switch to it. One branch for the entire batch.
- Loop: run `do-commit` until no planned tasks remain (task_get.py --include-planned returns exit code 1).
- Stops when no planned tasks remain.
