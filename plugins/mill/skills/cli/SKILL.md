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

## Timestamps

When a timestamp is needed in filenames, frontmatter, or metadata, **always generate it via shell** — never guess or hallucinate a timestamp.

- **Filenames** (compact, no punctuation): `date -u +"%Y%m%d-%H%M%S"` → `20260408-143052`
- **Metadata / ISO 8601**: `date -u +"%Y-%m-%dT%H:%M:%SZ"` → `2026-04-08T14:30:52Z`

Store the result in a variable when the same timestamp is needed in multiple places within one operation.
