---
name: helm-sync
description: Sync local kanban board state to GitHub Projects and issues.
---

# helm-sync

On-demand sync from local `.kanban.md` to GitHub Projects board. Optional --- Helm works fully offline without it.

---

## Entry

Check GitHub CLI is authenticated:

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

Read `_helm/config.yaml`.

---

## Steps

### Step 1: Ensure GitHub config

If `_helm/config.yaml` has no `github:` section (or it is incomplete), set it up now:

1. Detect repo: `gh repo view --json owner,name`
2. Check for existing projects: `gh project list --owner <owner> --format json`
3. Ask user which to use or create new.
4. Get the Status field ID: `gh project field-list <number> --owner <owner> --format json`
5. Configure Helm columns via GraphQL mutation (Backlog, In Progress, Done, Blocked).
6. Get the Project Node ID via GraphQL query.
7. Write all IDs to `_helm/config.yaml` under `github:`:

```yaml
github:
  owner: "<OWNER>"
  repo: "<REPO>"
  project-number: <NUMBER>
  project-node-id: "<PROJECT_NODE_ID>"
  status-field-id: "<STATUS_FIELD_ID>"
  columns:
    backlog: "<OPTION_ID>"
    in-progress: "<OPTION_ID>"
    done: "<OPTION_ID>"
    blocked: "<OPTION_ID>"
```

If `github:` section already exists and is complete, skip this step.

### Step 2: Read local board

Read `.kanban.md`. Parse all tasks and their current columns.

### Step 3: Sync tasks

For each task in `.kanban.md`:

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

3. **Set column** to match local kanban column:
   ```bash
   gh project item-edit --id <item-id> --project-id <project-node-id> --field-id <status-field-id> --single-select-option-id <column-option-id>
   ```

### Step 4: Report

```
Synced to GitHub:
  Tasks synced: <count>
  Issues created: <count>
  Board: https://github.com/users/<owner>/projects/<project-number>
```
