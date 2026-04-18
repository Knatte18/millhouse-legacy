# Home.md Format Reference

Reference for the `Home.md` file in the GitHub Wiki. This is the wiki-based task list that Mill skills read and write.

## File Location

`Home.md` lives in the GitHub Wiki (`<repo>.wiki.git`), cloned locally at `<worktree-parent>/<repo>.wiki/`. Each worktree accesses it via the `.mill/` junction at cwd: `.mill/Home.md`.

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
Google OAuth first. Must support token refresh.

[Background](add-oauth-support.md)
```

The description is a single prose sentence (not a bullet list). The Background link, if present, appears on its own paragraph (blank line before it).

## Phase Markers

Phase markers are optional. Skills write them when claiming a task; humans never need to add them manually.

Format: `## [phase] Task Title`

```markdown
## [s] Add OAuth Support
## [active] Add OAuth Support
## [completed] Add OAuth Support
## [done] Add OAuth Support
```

Valid phase values in `Home.md`: `s`, `active`, `completed`, `done`.

- No marker = unclaimed / available for pickup
- `[s]` = ready to be claimed by `mill-spawn` or `mill-start` (mnemonic: `s` for spawn)
- `[active]` = claimed and in progress — written by `mill-start` or `spawn_task.py` at claim time; stays in place through the entire discuss/plan/implement/test/review window until merge or abandon
- `[completed]` = task work complete, not yet merged — written by `mill-go` at Phase: Completion
- `[done]` = merged but not yet cleaned up — written by `mill-merge`, removed by `mill-cleanup` skill

There is no permanent `[abandoned]` phase. `mill-abandon` removes the `[active]` marker and deletes `active/<slug>/` from the wiki. The entry returns to an unmarked state (or is removed entirely).

Task identity is the title text *without* any `[phase]` prefix. `## [active] Add OAuth Support` → title = `Add OAuth Support`.

## Slug Derivation

The slug for a task equals the branch name (minus any configured `repo.branch-prefix/` prefix). Derive via `millpy.core.paths.slug_from_branch(cfg)`. Example: branch `mh/add-oauth-support` with prefix `mh` → slug `add-oauth-support`.

The slug is also used as the task directory name under `.mill/active/<slug>/` in the wiki.

## Task Block Boundaries

A task block starts at `## Title` (with or without `[phase]`) and ends immediately before the next `## `, or at EOF. When moving or reading tasks, capture the entire block.

## How Mill Uses Home.md

| Operation | What Mill does |
|-----------|---------------|
| **Create task** (mill-add) | Append `## Title` at end of file, commit + push via `tasks_md.write_commit_push` |
| **Claim task** (mill-start) | Add `[active]` marker to heading, commit + push via `tasks_md.write_commit_push` |
| **Spawn task** (mill-spawn) | Add `## [s] Title`, commit + push; `spawn_task.py` claims it (changes to `[active]`) |
| **Update phase** (mill-go) | Writes `[completed]` at Phase: Completion via `write_commit_push` |
| **Complete task** (mill-cleanup) | Remove `## ` block entirely via `write_commit_push` |
| **Abandon task** (mill-abandon) | Remove `[active]` marker and delete `active/<slug>/` from wiki |
| **Dashboard** (mill-status) | Read Home.md for task counts and phase overview |

## Write Rules

- `Home.md` is wiki-tracked. All changes require commit and push to the wiki repo.
- Use `## ` headings for tasks (not `###` or deeper).
- Descriptions are prose sentences (not bullet lists). No `- tags:` lines.
- Phase markers are optional — adding a task by hand requires only `## Title`.
- All skills (whether run from the main or a child worktree) read and write `Home.md` exclusively via `millpy.tasks.tasks_md.resolve_path(cfg)` and `millpy.tasks.tasks_md.write_commit_push(cfg, content, commit_msg)`. Never via `git` commands against the main worktree.
- Every orchestrator entry point calls `millpy.tasks.wiki.sync_pull(cfg)` before reading wiki state.

## Background Files

Each task may have a companion background file in the wiki. Background files hold detailed scope, design questions, open decisions, and context that would bloat the task index.

Convention:
- File name: slug derived from task title (e.g. `add-oauth-support.md`).
- Linked from the task block: `[Background](add-oauth-support.md)` on its own paragraph (blank line before it).
- Content: full prose — no format constraints beyond a `# Title` heading matching the task.
- Skills do not read or write background files. They are for humans and discussion threads.

Keep `Home.md` entries short: 1–2 description sentences and a background link. Detailed scope, design questions, and option analysis go in the background file.

## Example File

```markdown
# Tasks

## Add OAuth Support
Google OAuth first. Must support token refresh.

[Background](add-oauth-support.md)

## [active] Fix login validation
Input sanitization is missing on the login form.

## Update documentation
```
