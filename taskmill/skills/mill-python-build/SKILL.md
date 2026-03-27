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

## Import Organization

Organize imports in three tiers, separated by blank lines and labeled with comments:

```python
# Python packages
import datetime
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

# Domain packages
from solgt.timeseries import convert_date_to_t

# Local packages
import utils_config
import utils_file_io as fio
```

- Standard library first, then third-party, then local — each group with a section comment.
- Aliased imports are fine for frequently used modules (e.g., `import utils_file_io as fio`).
- No wildcard imports.

## Logging

- Configure logging at the module level using `logging.getLogger(__name__)`.
- Use structured format: `[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s`.
- Use appropriate levels: `info` for status, `warning` for recoverable issues, `error` for failures.
- Log messages should be descriptive with context: `"Extracting CBI into cube form..."`, not `"Processing..."`.

## Configuration

- Use a dedicated config module (e.g., `utils_config.py`) for constants and paths.
- Load environment variables with `dotenv` and construct paths using `pathlib.Path`.
- Group constants by purpose with section comments: tweakable parameters, file paths, external config.

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
