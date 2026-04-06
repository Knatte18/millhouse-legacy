---
name: cli
description: Shell command guidelines. Use when running shell commands.
---

# CLI Skill

Guidelines for shell commands executed by CC.

---

- Use **absolute paths** instead of `cd`. For git: `git -C /path/to/repo status` instead of `cd /path && git status`.
- Use **long flag names**: `--message` instead of `-m`, `--verbose` instead of `-v`.
- **Never use `rm -rf` or `rm -fr`.** Use `rm -r` (without `-f`). If a file is write-protected, the interactive prompt is intentional — stop and investigate rather than forcing deletion.
