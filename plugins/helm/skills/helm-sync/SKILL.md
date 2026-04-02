---
name: helm-sync
description: Sync local kanbn board state to GitHub Projects and issues.
---

# helm-sync

On-demand sync from local `.kanbn/index.md` to GitHub Projects board and issues. This skill is optional --- Helm works fully offline without it.

---

## Entry

Read `_helm/config.yaml`. The `github:` section must exist with `owner`, `repo`, `project-number`, `project-node-id`, `status-field-id`, and `columns`. If missing, stop: "GitHub config not set. Add `github:` section to `_helm/config.yaml` or re-run `helm-setup`."

Check GitHub CLI is authenticated:

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

---

## Steps

### Step 1: Read local board

Read `.kanbn/index.md`. Parse all tasks and their current columns.

### Step 2: Ensure GitHub Project exists

Check for an existing project linked to this repo:

```bash
gh project list --owner <owner> --format json
```

If no project exists or `project-number` is not in config:
1. Create: `gh project create --title "<repo>" --owner <owner> --format json`
2. Link: `gh project link <number> --owner <owner> --repo <owner>/<repo>`
3. Configure Helm columns via GraphQL (same as old helm-setup Step 4).
4. Save `project-number`, `project-node-id`, `status-field-id`, and column option IDs to `_helm/config.yaml` under `github:`.

### Step 3: Sync tasks

For each task in `.kanbn/index.md`:

1. **Find or create GitHub issue.** Search for an existing issue with matching title:
   ```bash
   gh issue list --repo <owner>/<repo> --search "<title>" --json number,title --limit 5
   ```
   - If found: use that issue number.
   - If not found: create one:
     ```bash
     gh issue create --title "<title>" --body "" --repo <owner>/<repo>
     ```

2. **Add to project board** (if not already):
   ```bash
   gh project item-add <project-number> --owner <owner> --url <issue-url> --format json
   ```

3. **Set column** to match local kanbn column:
   ```bash
   gh project item-edit --id <item-id> --project-id <project-node-id> --field-id <status-field-id> --single-select-option-id <column-option-id>
   ```

### Step 4: Sync plan comments

If `_helm/scratch/status.md` exists and has a `plan:` field, read the plan file. If the plan is approved and no sync comment has been posted yet, post the plan summary as a comment on the linked issue:

```bash
gh issue comment <issue-number> --repo <owner>/<repo> --body "<plan summary>"
```

### Step 5: Report

```
Synced to GitHub:
  Project: <repo> (#<number>)
  Tasks synced: <count>
  Issues created: <count>
  Board: https://github.com/users/<owner>/projects/<number>
```
