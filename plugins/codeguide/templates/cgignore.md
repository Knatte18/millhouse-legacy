# Codeguide Ignore

Directories that are not source code. Codeguide skips these entirely — no scanning, no docs, no mentions in Overview.md.

Patterns follow .gitignore conventions: `pi_data/` matches at any depth, `/pi_data/` matches only at the root level.

- __pycache__/
- .venv/
- venv/
- env/
- node_modules/
- obj/
- bin/
- dist/
- build/
- .git/
- .tox/
- .pytest_cache/
- .mypy_cache/
- _codeguide/
- .llm/
- RunOutput/
