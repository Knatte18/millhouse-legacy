---
name: mill-python-comments
description: Docstring and inline comment rules for Python. Use when writing Python comments.
---

# Comments and Documentation Skill

Guidelines for docstrings and comments in Python.

---

## Module docstrings

- Every `.py` file **must** have a module-level docstring.
- Describe the module's purpose in plain narrative prose.
- List key functions or classes if the module contains more than a few.

## Function and class docstrings

- Public functions and classes should have a one-line docstring summarizing what they do.
- Keep it concise — one sentence, no blank lines after the opening `"""`.
- Do **not** add `Args:`, `Returns:`, or `Raises:` sections. The signature and type hints convey parameter information.
- Omit docstrings on trivial functions where the name and signature are self-explanatory.

## Inline comments

- Use inline comments only to explain **why** or to clarify non-obvious logic.
- Write in imperative style: "Convert to...", "Find the...", "Remove entries where...".
- Place comments on their own line above the code, not at the end of a line.
- If the code needs a "what" comment, the code itself is unclear — refactor instead.

## Prohibited patterns

- **Never** comment out code. Delete it. Version control handles history.
- **No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").
- **No redundant docstrings** that restate the function name: `def load_data` does not need `"""Load data."""`.
