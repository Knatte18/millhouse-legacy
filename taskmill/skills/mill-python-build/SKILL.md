---
name: mill-python-build
description: Build and test commands for Python projects. Use after completing a task.
---

# Build Skill

Build, lint, and test configuration for Python projects.

---

## Build Commands

Run these commands after completing a task to verify correctness:

```bash
ruff check .
pytest
```

## Failure Handling

- If **ruff fails**: fix the linting violations and retry. Do not add `noqa` suppression unless the rule is genuinely inapplicable.
- If **tests fail**: analyze the failure, fix the code or test, and retry.
- If a fix requires changes beyond the current task's scope: stop and report the issue to the user.
- Do **not** skip or disable failing tests.

---

## Project Configuration

> Customize per project. Specify test paths, ruff config, and virtual environment setup.

### Defaults

- Run `ruff check .` from the project root.
- Run `pytest` from the project root (discovers tests automatically).

### Per-project overrides

Specify these when the defaults don't apply:

- Test directory or specific test files
- Ruff configuration file path
- Additional pytest flags (e.g. `-x` for fail-fast, `--cov` for coverage)
- Virtual environment activation command

<!-- Project-specific build configuration goes here -->
