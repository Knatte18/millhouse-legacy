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
## [discussing] Add OAuth Support
## [implementing] Add OAuth Support
## [testing] Add OAuth Support
## [reviewing] Add OAuth Support
```

Valid phase values: `discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `pr-pending`, `done`, `>`.

- No marker = unclaimed / available for pickup
- `[>]` = ready to be claimed by `mill-spawn.ps1` (changed to `[discussing]` when claimed)
- `[done]` = merged but not yet cleaned up — set by `mill-merge`, removed by `mill-cleanup.ps1`
- Other markers = active work in progress

Task identity is the title text *without* any `[phase]` prefix. `## [implementing] Add OAuth Support` -> title = `Add OAuth Support`.

Slug for branch names: derived from title (without phase), lowercase, spaces to hyphens, remove special characters. "Add OAuth Support" -> `add-oauth-support`.

## Task Block Boundaries

A task block starts at `## Title` (with or without `[phase]`) and ends immediately before the next `## `, or at EOF. When moving or reading tasks, capture the entire block.

## How Mill Uses tasks.md

| Operation | What Mill does |
|-----------|---------------|
| **Create task** (mill-add) | Append `## Title` at end of file, commit + push |
| **Import issues** (mill-inbox) | Append `## Title` blocks at end of file, commit + push |
| **Claim task** (mill-start) | Add `[discussing]` marker to heading, commit + push |
| **Spawn task** (mill-spawn) | Add `## [>] Title`, commit + push; script claims it (changes to `[discussing]`) |
| **Update phase** (mill-go) | Update `[phase]` marker in heading, commit + push on parent |
| **Complete task** (mill-cleanup) | Remove `## ` block entirely via `mill-cleanup.ps1`, commit + push on parent |
| **Abandon task** (mill-abandon) | Remove `[phase]` marker from heading, commit + push on parent |
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

## [implementing] Fix login validation
- Input sanitization is missing on the login form.

## Update documentation
```
