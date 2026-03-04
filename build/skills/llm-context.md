# LLM Context Skill

Rules for directory structure, file placement, and scratch file management.

---

## Directory Structure (per sub-project)

```
<project>/
├── doc/
│   ├── backlog.md        ← Tracked. High-level task list with [ ]/[>]/[p]/[!]/[x] states.
│   └── changelog.md      ← Tracked. Dated log of completed work.
└── .llm/                 ← Untracked. Plans, scratch files, working details.
    └── plans/
        └── YYYY-MM-DD-HHMM-<slug>.md  ← Detailed implementation plans with [ ]/[x] steps.
```

## Rules

- `.llm/` is **never** committed. It must be in `.gitignore` via `**/.llm/`.
- `doc/backlog.md` and `doc/changelog.md` are **tracked** in version control.
- Plans are stored in `.llm/plans/YYYY-MM-DD-HHMM-<slug>.md` (date and time are UTC at plan creation).
- When creating `.llm/` for the first time, verify that `**/.llm/` is in `.gitignore`.

## File Writing Policy

- **Never** write to `/tmp` or system temporary directories (causes permission prompts).
- Use `.llm/` for all scratch files, intermediate output, and temporary data.
