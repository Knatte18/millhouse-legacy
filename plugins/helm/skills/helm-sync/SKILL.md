---
name: helm-sync
description: Sync local kanbn board state to GitHub Projects and issues.
---

# helm-sync

On-demand sync from local `.kanbn/index.md` to GitHub Projects board. This skill is optional --- Helm works fully offline without it.

---

## Entry

Read `_helm/config.yaml`. The `github:` section must exist with `owner`, `repo`, `project-number`, `project-node-id`, `status-field-id`, and `columns`. If missing, stop: "GitHub config incomplete. Run `helm-setup` with `gh` authenticated to provision GitHub fields."

Check GitHub CLI is authenticated:

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

---

## Steps

### Step 1: Read local board

Read `.kanbn/index.md`. Parse all tasks and their current columns.

### Step 2: Sync tasks

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

### Step 3: Report

```
Synced to GitHub:
  Tasks synced: <count>
  Issues created: <count>
  Board: https://github.com/users/<owner>/projects/<project-number>
```
