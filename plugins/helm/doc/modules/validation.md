# Validation Rules

Post-write validation for kanban board files and `_helm/config.yaml`. Skills that write to these files must validate after writing. Rules are structural only — they catch broken file format, not invalid metadata values.

## Kanban Board Files (`kanbans/*.kanban.md`)

### Directory validation

1. **All 4 files must exist.** The `kanbans/` directory must contain: `backlog.kanban.md`, `processing.kanban.md`, `done.kanban.md`, `blocked.kanban.md`.

### Per-file validation

After writing any board file, verify all of the following:

1. **Single project heading.** Exactly one `#` heading, at line 1.
2. **Correct column.** Exactly one `##` heading, matching the file's designated column:
   - `backlog.kanban.md` → `## Backlog`
   - `processing.kanban.md` → `## In Progress`
   - `done.kanban.md` → `## Done`
   - `blocked.kanban.md` → `## Blocked`
3. **No extra columns.** No `##` headings beyond the one designated column.
4. **Tasks under column.** Every `###` heading appears after the `##` heading (no orphaned tasks before the column).
5. **No stray content.** No non-blank lines between the `#` heading and the `##` heading.

## _helm/config.yaml

After writing, verify all of the following:

1. **Valid YAML.** The file parses without errors.
2. **Required top-level keys.** These keys must be present: `worktree`, `models`, `notifications`.
3. **GitHub section (if present).** If a `github:` key exists, it must contain `owner` and `repo` sub-keys.

Sub-keys under `worktree`, `models`, and `notifications` are not validated — new fields can be added without updating these rules.

## Failure behavior

If validation fails: report the specific rule violation to the user and stop. Do not attempt to auto-fix — automatic corrections risk making the problem worse.
