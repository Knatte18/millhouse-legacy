---
name: helm-sync
description: Import GitHub issues into the local backlog.
---

# helm-sync

One-way import: GitHub issues with the `helm` label → `kanbans/backlog.kanban.md` Backlog column. Issues are closed after import to keep the inbox clean.

---

## Entry

Check GitHub CLI is authenticated:

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

Read `_helm/config.yaml`. If no `github:` section exists, detect repo:

```bash
gh repo view --json owner,name
```

Write `owner` and `repo` to `_helm/config.yaml` under `github:`:

```yaml
github:
  owner: "<OWNER>"
  repo: "<REPO>"
```

Validate `_helm/config.yaml` per `doc/modules/validation.md`. If validation fails, report the issue to the user and stop.

---

## Steps

### Step 1: Fetch labeled issues

```bash
gh issue list --repo <owner>/<repo> --label "helm" --state open --json number,title,body --limit 50
```

If no issues found: report "No open issues with label `helm`. Nothing to import." Stop.

### Step 2: Deduplicate

Read `kanbans/backlog.kanban.md`. Collect all `###` headings from all columns (Backlog, Spawn, Delete). Strip any `[phase]` suffix from headings before comparing.

For each fetched issue: check if the title (case-insensitive) matches an existing task heading. If match found: skip import but still close the issue (already imported — keep inbox clean).

### Step 3: Import new issues

For each issue NOT already in backlog:

Add a new task block under `## Backlog` in `kanbans/backlog.kanban.md`:

```markdown
### <Issue title>

    ```md
    <Issue body, or "Imported from GitHub issue #N" if body is empty>
    ```
```

### Step 4: Close imported issues

For each issue that was imported OR matched an existing task:

```bash
gh issue close <number> --repo <owner>/<repo>
```

### Step 5: Validate, commit, and push

If zero new issues were imported (all fetched issues were duplicates), skip the commit and push — the backlog file is unchanged.

Otherwise, validate `kanbans/backlog.kanban.md` per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). If validation fails, report the issue to the user and stop before committing.

Then commit and push:

```bash
git add kanbans/backlog.kanban.md
git commit -m "sync: import <N> issues from GitHub"
git push
```

### Step 6: Report

```
Imported from GitHub:
  New tasks:     <count>
  Already in backlog: <count> (issues closed)
  Total closed:  <count>
```
