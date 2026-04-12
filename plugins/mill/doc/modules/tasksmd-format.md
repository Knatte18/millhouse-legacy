# tasks.md Format Reference

Reference for the `tasks.md` file at the repository root. This is the git-tracked task list that Mill skills read and write.

## File Location

`tasks.md` in the project root (the working directory where `_millhouse/` lives). Git-tracked — changes require commit and push.

Created by `mill-setup`. Must have a `# Tasks` heading on line 1.

## Task Format

Tasks use `## ` headings. Each task is a block from `## ` to the next `## ` or EOF.

### Minimal task (what mill-add creates)

```markdown
## Add OAuth Support
```

### Task with description

```markdown
## Add OAuth Support
- Google OAuth first. Must support token refresh.
- Multi-line descriptions as bullet points.
```

### Task with tags

```markdown
## Add OAuth Support
- tags: [auth, backend]
- Google OAuth first. Must support token refresh.
```

## Phase Markers

Phase markers are optional. Skills write them when claiming a task; humans never need to add them manually.

Format: `## [phase] Task Title`

```markdown
## [>] Add OAuth Support
## [active] Add OAuth Support
## [done] Add OAuth Support
## [abandoned] Add OAuth Support
```

Valid phase values in `tasks.md`: `>`, `active`, `done`, `abandoned`.

- No marker = unclaimed / available for pickup
- `[>]` = ready to be claimed by `mill-spawn.ps1` or `mill-start`
- `[active]` = claimed and in progress — written by `mill-start` or `mill-spawn.ps1` at claim time; stays in place through the entire discuss/plan/implement/test/review window until merge or abandon
- `[done]` = merged but not yet cleaned up — written by `mill-merge`, removed by `mill-cleanup` skill
- `[abandoned]` = task abandoned, awaiting cleanup — written by `mill-abandon`, removed by `mill-cleanup` skill

> **Note:** Valid phase values in `status.md`'s `phase:` field (a separate vocabulary) remain unchanged: `discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `pr-pending`, `complete`. Only the `tasks.md` marker set is trimmed. Two separate validation domains.

Task identity is the title text *without* any `[phase]` prefix. `## [active] Add OAuth Support` -> title = `Add OAuth Support`.

Slug for branch names: derived from title (without phase), lowercase, spaces to hyphens, remove special characters. "Add OAuth Support" -> `add-oauth-support`.

## Task Block Boundaries

A task block starts at `## Title` (with or without `[phase]`) and ends immediately before the next `## `, or at EOF. When moving or reading tasks, capture the entire block.

## How Mill Uses tasks.md

| Operation | What Mill does |
|-----------|---------------|
| **Create task** (mill-add) | Append `## Title` at end of file, commit + push |
| **Import issues** (mill-inbox) | Append `## Title` blocks at end of file, commit + push |
| **Claim task** (mill-start) | Add `[active]` marker to heading, commit + push |
| **Spawn task** (mill-spawn) | Add `## [>] Title`, commit + push; script claims it (changes to `[active]`) |
| **Update phase** (mill-go) | mill-go does not update the `[phase]` marker in tasks.md; the `[active]` marker written at claim time remains until merge or abandon |
| **Complete task** (mill-cleanup) | Remove `## ` block entirely via `mill-cleanup` skill, commit + push on parent |
| **Abandon task** (mill-abandon) | Replace `[phase]` marker with `[abandoned]` marker, commit + push on parent (via merge-lock) |
| **Dashboard** (mill-status) | Read tasks.md for task counts and phase overview |

## Write Rules

- `tasks.md` is git-tracked. All changes require commit and push.
- Use `## ` headings for tasks (not `###`).
- Descriptions use bullet points (not fenced code blocks).
- Phase markers are optional — adding a task by hand requires only `## Title`.
- Skills that run from child worktrees modify the parent's `tasks.md` (resolve parent path via `git worktree list --porcelain`).
- Skills that run from the main worktree modify `tasks.md` directly in the project root.

## Example File

```markdown
# Tasks

## Add OAuth Support
- Google OAuth first. Must support token refresh.
- tags: [auth, backend]

## [active] Fix login validation
- Input sanitization is missing on the login form.

## Update documentation
```
