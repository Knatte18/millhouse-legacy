# tasks.md Format Reference

Reference for the `tasks.md` file on the orphan `tasks` branch. This is the git-tracked task list that Mill skills read and write.

## File Location

`tasks.md` lives on the orphan branch `tasks`, checked out as a persistent git worktree at the path configured in `_millhouse/config.yaml` → `tasks.worktree-path` (typically `<parent-of-repo>/<reponame>.worktrees/tasks`). The branch never merges into `main`.

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
## [s] Add OAuth Support
## [active] Add OAuth Support
## [completed] Add OAuth Support
## [done] Add OAuth Support
## [abandoned] Add OAuth Support
```

Valid phase values in `tasks.md`: `s`, `active`, `completed`, `done`, `abandoned`.

- No marker = unclaimed / available for pickup
- `[s]` = ready to be claimed by `mill-spawn` or `mill-start` (mnemonic: `s` for spawn)
- `[active]` = claimed and in progress — written by `mill-start` or `mill-spawn.ps1` at claim time; stays in place through the entire discuss/plan/implement/test/review window until merge or abandon
- `[completed]` = task work complete, not yet merged — written by `mill-go` at Phase: Completion (sub-steps 12.b and 12.d)
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
| **Create task** (mill-add) | Append `## Title` at end of file on the tasks branch, commit + push |
| **Claim task** (mill-start) | Add `[active]` marker to heading on the tasks branch, commit + push |
| **Spawn task** (mill-spawn) | Add `## [s] Title`, commit + push; script claims it (changes to `[active]`) |
| **Update phase** (mill-go) | Writes `[completed]` at Phase: Completion (sub-steps 12.b and 12.d) via `write_commit_push` |
| **Complete task** (mill-cleanup) | Remove `## ` block entirely via `write_commit_push` against the tasks worktree |
| **Abandon task** (mill-abandon) | Replace `[phase]` marker with `[abandoned]` marker via `write_commit_push` against the tasks worktree |
| **Dashboard** (mill-status) | Read tasks.md for task counts and phase overview |

## Write Rules

- `tasks.md` is git-tracked. All changes require commit and push.
- Use `## ` headings for tasks (not `###`).
- Descriptions use bullet points (not fenced code blocks).
- Phase markers are optional — adding a task by hand requires only `## Title`.
- All skills (whether run from the main or a child worktree) read and write `tasks.md` exclusively via `millpy.tasks.tasks_md.resolve_path` and `millpy.tasks.tasks_md.write_commit_push` against the dedicated tasks worktree. Never via `git` commands in the current worktree.

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
