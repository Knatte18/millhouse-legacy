---
name: mill-inbox
description: Review fetched GitHub issues and select which to import into tasks.md.
---

# mill-inbox

Interactive. Review issues fetched by `fetch-issues.ps1` and select which ones to import into `tasks.md`. Selected issues are added to `tasks.md` and closed on GitHub.

---

## Entry

Check GitHub CLI is authenticated:

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

Verify `tasks.md` exists in the project root (the working directory where `_millhouse/` lives). If not, stop and tell the user to run `mill-setup` first.

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

Read `tasks.md` in the project root. Collect all `## ` headings. Strip any `[phase] ` prefix from headings before comparing.

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

For each selected issue, append a task block at the end of `tasks.md`:

If the issue has labels (the `labels` field is a non-empty array of objects with `name` properties), add a `- tags:` line after the heading:

With labels and body:

```markdown
## <issue title>
- tags: [label1, label2]
- <first paragraph of issue body>
```

With labels, no body:

```markdown
## <issue title>
- tags: [label1, label2]
```

Without labels, with body:

```markdown
## <issue title>
- <first paragraph of issue body>
```

Without labels, no body:

```markdown
## <issue title>
```

### Step 5: Close selected issues on GitHub

For each selected issue:

```bash
gh issue close <number> --repo <repo>
```

Where `<repo>` is the `repo` field from `issues.json`.

### Step 6: Validate

Validate `tasks.md` per `plugins/mill/doc/modules/validation.md` (tasks.md structural rules). If validation fails, report the violation and stop.

### Step 7: Commit and push

```bash
git add tasks.md
git commit -m "task: import <N> issues from GitHub"
git push
```

### Step 8: Report

```
<N> issues imported to tasks.md, <N> closed on GitHub.
```
