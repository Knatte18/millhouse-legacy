# Kanban — GitHub Projects V2

GitHub Projects V2 is the single source of truth for task tracking. No local backlog files.

## Why GitHub Projects

- Built into GitHub (not 3rd party). Free for all plans.
- Team visibility — non-CC team members see progress without terminal access.
- Issues support rich markdown bodies — title + any amount of context.
- Managed via `gh` CLI — CC can read and update programmatically.

## Board Structure

One board per repo. Columns:

| Column | Meaning |
|--------|---------|
| **Backlog** | Task exists, not started |
| **Discussing** | `helm-start` claimed the task, discuss in progress |
| **Planned** | Plan approved, ready for `helm-go` |
| **Implementing** | `helm-go` is executing |
| **Reviewing** | Code review in progress |
| **Blocked** | Needs user input or upstream fix |
| **Done** | Completed and committed (or merged) |

## Setup (helm-setup skill)

One-time per repo. Run `helm-setup` to automate.

### Step 1: Prerequisites

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

### Step 2: Create project

```bash
gh project create --title "<repo-name>" --owner <owner> --format json
```

Parse the JSON output to get the project `number`. Then link to the repo:

```bash
gh project link <number> --owner <owner> --repo <owner>/<repo>
```

### Step 3: Get the Status field ID

```bash
gh project field-list <number> --owner <owner> --format json | jq '.fields[] | select(.name == "Status") | .id'
```

### Step 4: Configure Status columns

Replace the default columns (Todo/In Progress/Done) with Helm phases via GraphQL:

```bash
gh api graphql -f query='
  mutation {
    updateProjectV2Field(input: {
      fieldId: "<STATUS_FIELD_ID>"
      singleSelectOptions: [
        {name: "Backlog", color: GRAY, description: ""},
        {name: "Discussing", color: BLUE, description: ""},
        {name: "Planned", color: PURPLE, description: ""},
        {name: "Implementing", color: YELLOW, description: ""},
        {name: "Reviewing", color: ORANGE, description: ""},
        {name: "Blocked", color: RED, description: ""},
        {name: "Done", color: GREEN, description: ""}
      ]
    }) {
      projectV2Field {
        ... on ProjectV2SingleSelectField {
          id
          options { id name color }
        }
      }
    }
  }'
```

Parse the response to get option IDs for each column.

### Step 5: Get the Project Node ID

```bash
gh api graphql -f query='
  query {
    user(login: "<owner>") {
      projectV2(number: <number>) {
        id
      }
    }
  }'
```

Detect owner type first: `gh api users/<owner> --jq '.type'` returns `"User"` or `"Organization"`. Use `user()` or `organization()` accordingly.

### Step 6: Create directory structure and config

```bash
mkdir -p _helm/knowledge _helm/scratch/plans _helm/scratch/briefs
```

Write `_helm/config.yaml` (this is the canonical config template — all config lives here):

```yaml
worktree:
  branch-template: "<user-provided, e.g. hanf/{parent-slug}/{slug} or just {slug}>"
  path-template: "../{slug}"

github:
  owner: "<owner>"
  repo: "<repo>"
  project-number: <number>
  project-node-id: "<PROJECT_NODE_ID>"
  status-field-id: "<STATUS_FIELD_ID>"
  columns:
    backlog: "<OPTION_ID>"
    discussing: "<OPTION_ID>"
    planned: "<OPTION_ID>"
    implementing: "<OPTION_ID>"
    reviewing: "<OPTION_ID>"
    blocked: "<OPTION_ID>"
    done: "<OPTION_ID>"

models:
  session: opus
  plan-review: sonnet
  code-review: sonnet
  explore: haiku

notifications:
  slack:
    enabled: false
    webhook: ""
    channel: ""
  toast:
    enabled: true
```

### Step 7: Update .gitignore

Add `_helm/scratch/` if not already present.

### Step 8: Ask for branch template

Ask the user: "Branch naming template? Examples: `hanf/{parent-slug}/{slug}` (team repo), `{slug}` (solo repo)"

Store in `_helm/config.yaml` under `worktree.branch-template`.

### Step 9: Report

```
Helm initialized:
  Project: <repo-name> (#<number>)
  Board: <url>
  Config: _helm/config.yaml
  Prefix: <prefix>

Switch to Board layout in GitHub (click layout dropdown) to see kanban columns.
Run helm-add to create your first task.
```

## Task Lifecycle

### Creating tasks

Via `helm-add`:
```bash
gh issue create --title "Add OAuth support" --body "Google OAuth first. Must support token refresh."
gh project item-add <project-id> --url <issue-url>
```

Or manually in GitHub UI — CC reads from the board regardless of how tasks were created.

### Reading tasks

`helm-start` reads from the board:
```bash
gh project item-list <number> --owner <owner> --format json
```

Filters to Backlog column (or user-specified column). Lists them numbered for user selection.

### Updating status

At each phase transition, CC moves the card:
```bash
gh project item-edit --id <item-id> --project-id <project-node-id> --field-id <status-field-id> --single-select-option-id <option-id>
```

### Commenting

CC posts progress comments on the issue:
```bash
gh issue comment <number> --repo <repo> --body "Plan approved. Starting implementation."
```

Useful for: plan approval, implementation progress, review results, blockers, completion summary.

### Worktree metadata

When a task spawns a worktree, CC posts a comment:
```
Worktree: feature/auth-oauth
Parent: feature/auth
Branch: feature/auth-oauth
```

This links the GitHub issue to the physical worktree for `helm-status` cross-referencing.

## Sub-tasks

Tasks within a worktree that are too small for their own GitHub issue can be tracked as a checklist in the parent issue body:

```markdown
## Sub-tasks
- [x] Create OAuth client wrapper
- [ ] Add callback endpoint
- [ ] Write integration tests
```

CC updates these checkboxes via `gh issue edit` as steps complete. GitHub renders the progress bar automatically.

For sub-tasks large enough to warrant their own worktree: create a new issue, link it to the parent with "Part of #57", and spawn the worktree.

## Offline Consideration

CC requires network access anyway. If GitHub is unreachable, `helm-add` and kanban updates fail gracefully — tasks are not lost (they exist as issues already), and CC can retry when connectivity returns.
