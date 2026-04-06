---
name: mill-inbox
description: Review fetched GitHub issues and select which to import into the backlog.
---

# mill-inbox

Interactive. Review issues fetched by `fetch-issues.ps1` and select which ones to import into the local backlog. Selected issues are added to `_millhouse/backlog.kanban.md` and closed on GitHub.

---

## Entry

Check GitHub CLI is authenticated:

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

Verify `_millhouse/backlog.kanban.md` exists. If not, stop and tell the user to run `mill-setup` first.

Read `_millhouse/scratch/issues.json`. If the file does not exist, stop and tell the user:

```
No issues file found. Run fetch-issues.ps1 first:
  .\_millhouse\fetch-issues.ps1
```

---

## Steps

### Step 1: Display freshness

Read the `fetchedAt` field from `_millhouse/scratch/issues.json`. Display it to the user so they know how fresh the data is:

```
Issues fetched at: <fetchedAt>
```

### Step 2: Deduplicate

Read `_millhouse/backlog.kanban.md`. Collect all `###` headings from all columns (Backlog, Spawn, Delete). Strip any `[phase]` suffix from headings before comparing.

For each issue in `issues.json`: check if the title (case-insensitive) matches an existing task heading. Deduplicated issues are silently excluded from the selection list and are NOT closed on GitHub.

### Step 3: Present issues

If no new issues remain after dedup: report "No new issues to import." and stop.

Parse the `repo` field from `issues.json` (used later for closing issues).

Present new issues as a numbered list. Do NOT use AskUserQuestion — use a numbered text list:

```
N) #<number> — <title> [label1, label2]
   <first line of body, truncated to ~80 chars>
```

If the issue has labels, show them in brackets after the title. The `labels` field in `issues.json` is an array of objects with a `name` property (e.g. `[{"name": "bug"}]`). If no labels, omit the brackets.

The user types:
- Numbers, comma-separated (e.g. `1, 3, 5`) to select specific issues
- `all` to select everything
- `none` to cancel

### Step 4: Import selected issues

For each selected issue, append a task block under `## Backlog` in `_millhouse/backlog.kanban.md`:

If the issue has labels (the `labels` field is a non-empty array of objects with `name` properties), add a `- tags:` metadata line after the heading. Extract label names and format as `- tags: [label1, label2]`. If no labels, omit the tags line.

If the issue body is empty or whitespace-only, with labels:

```markdown
### <issue title>
- tags: [label1, label2]
```

Without labels:

```markdown
### <issue title>
```

If the issue has a non-empty body, use an indented ` ```md ` code block (plain text descriptions are not parsed by the kanban.md extension and are destroyed on drag-and-drop). Tags go between the heading and the description block:

With labels:

```markdown
### <issue title>
- tags: [label1, label2]

    ```md
    <issue body>
    ```
```

Without labels:

```markdown
### <issue title>

    ```md
    <issue body>
    ```
```

### Step 5: Close selected issues on GitHub

For each selected issue:

```bash
gh issue close <number> --repo <repo>
```

Where `<repo>` is the `repo` field from `issues.json`.

### Step 6: Validate, commit, and push

Validate `_millhouse/backlog.kanban.md` per `plugins/mill/doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). If validation fails, report the violation and stop.

Since backlog is git-tracked:

```bash
git add _millhouse/backlog.kanban.md
git commit -m "sync: import <N> issues from inbox"
git push
```

### Step 7: Report

```
<N> issues imported to Backlog, <N> closed on GitHub.
```
