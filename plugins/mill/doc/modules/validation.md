# Validation Rules

Post-write validation for `tasks.md`, `_millhouse/scratch/status.md`, and `_millhouse/config.yaml`. Skills that write to these files must validate after writing. Rules are structural only — they catch broken file format, not invalid metadata values.

## tasks.md (repo root)

### File validation

1. **File must exist.** `tasks.md` must exist at the repository root (resolve via `git rev-parse --show-toplevel`). Created by `mill-setup`. If missing, run `mill-setup`.

### Structural validation

After writing tasks.md, verify all of the following:

1. **Single project heading.** Exactly one `# ` heading, at line 1 (e.g., `# Tasks`).
2. **Tasks use `## ` headings.** All task entries are `## ` headings (not `###` or deeper).
3. **Valid phase markers.** If a `## ` heading contains a `[phase]` marker, the phase must be one of: `discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `spawn`. Format: `## [phase] Title`.
4. **No orphaned content.** No non-blank lines before the first `## ` heading (except the `# ` project heading).

## status.md (`_millhouse/scratch/status.md`)

### Field validation

After writing status.md, verify:

1. **`phase:` is valid.** Must be one of: `discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `complete`. Empty/missing `phase:` is allowed only if no task is active.
2. **`task:` is non-empty when phase is set.** If `phase:` has a value, `task:` must also have a non-empty value.

## _millhouse/config.yaml

After writing, verify all of the following:

1. **Valid YAML.** The file parses without errors.
2. **Required top-level keys.** These keys must be present: `models`, `notifications`.
3. **GitHub section (deprecated).** If a `github:` key exists, it is ignored. No validation required.

Sub-keys under `models` and `notifications` are not validated — new fields can be added without updating these rules.

## Failure behavior

If validation fails: report the specific rule violation to the user and stop. Do not attempt to auto-fix — automatic corrections risk making the problem worse.
