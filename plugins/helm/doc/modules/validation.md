# Validation Rules

Post-write validation for the kanban board file and `_helm/config.yaml`. Skills that write to these files must validate after writing. Rules are structural only — they catch broken file format, not invalid metadata values.

## Kanban Board File (`kanbans/board.kanban.md`)

### File validation

1. **File must exist.** `kanbans/board.kanban.md` must exist. It is gitignored and local-only. On fresh clones, the file will not exist until `helm-setup` is run.

### Structural validation

After writing the board file, verify all of the following:

1. **Single project heading.** Exactly one `#` heading, at line 1.
2. **All five columns present.** Exactly five `##` headings, in order: `## Backlog`, `## Spawn`, `## In Progress`, `## Done`, `## Blocked`.
3. **No extra columns.** No `##` headings beyond the five designated columns.
4. **Tasks under columns.** Every `###` heading appears after a `##` heading (no orphaned tasks before the first column).
5. **No stray content.** No non-blank lines between the `#` heading and the first `##` heading.

## _helm/config.yaml

After writing, verify all of the following:

1. **Valid YAML.** The file parses without errors.
2. **Required top-level keys.** These keys must be present: `models`, `notifications`.
3. **GitHub section (if present).** If a `github:` key exists, it must contain `owner` and `repo` sub-keys.

Sub-keys under `models` and `notifications` are not validated — new fields can be added without updating these rules.

## Failure behavior

If validation fails: report the specific rule violation to the user and stop. Do not attempt to auto-fix — automatic corrections risk making the problem worse.
