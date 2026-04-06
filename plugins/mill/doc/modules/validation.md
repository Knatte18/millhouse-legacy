# Validation Rules

Post-write validation for the kanban board files and `_millhouse/config.yaml`. Skills that write to these files must validate after writing. Rules are structural only — they catch broken file format, not invalid metadata values.

## Backlog Board (`_millhouse/backlog.kanban.md`)

### File validation

1. **File must exist.** `_millhouse/backlog.kanban.md` must exist. It is git-tracked. On fresh clones, the file exists from git checkout. If missing, run `mill-setup`.

### Structural validation

After writing the backlog board, verify all of the following:

1. **Single project heading.** Exactly one `#` heading, at line 1.
2. **All three columns present.** Exactly three `##` headings, in order: `## Backlog`, `## Spawn`, `## Delete`.
3. **No extra columns.** No `##` headings beyond the three designated columns.
4. **Tasks under columns.** Every `###` heading appears after a `##` heading (no orphaned tasks before the first column).
5. **No stray content.** No non-blank lines between the `#` heading and the first `##` heading.

## Work Board (`_millhouse/scratch/board.kanban.md`)

### File validation

1. **File must exist** (when validating after a write). `_millhouse/scratch/board.kanban.md` is gitignored and local-only. On fresh clones, the file will not exist until `mill-setup` is run or `mill-start` creates it on first task claim.

### Structural validation

After writing the work board, verify all of the following:

1. **Single project heading.** Exactly one `#` heading, at line 1.
2. **All six columns present.** Exactly six `##` headings, in order: `## Discussing`, `## Planned`, `## Implementing`, `## Testing`, `## Reviewing`, `## Blocked`.
3. **No extra columns.** No `##` headings beyond the six designated columns.
4. **Tasks under columns.** Every `###` heading appears after a `##` heading (no orphaned tasks before the first column).
5. **No stray content.** No non-blank lines between the `#` heading and the first `##` heading.

## _millhouse/config.yaml

After writing, verify all of the following:

1. **Valid YAML.** The file parses without errors.
2. **Required top-level keys.** These keys must be present: `models`, `notifications`.
3. **GitHub section (deprecated).** If a `github:` key exists, it is ignored. No validation required.

Sub-keys under `models` and `notifications` are not validated — new fields can be added without updating these rules.

## Failure behavior

If validation fails: report the specific rule violation to the user and stop. Do not attempt to auto-fix — automatic corrections risk making the problem worse.
