---
name: helm-setup
description: Initialize Helm for a repository. Creates config, GitHub Project board, and directory structure.
---

# helm-setup

One-time initialization per repo. Creates the GitHub Project board, configures kanban columns, and writes `_helm/config.yaml`.

**Prerequisite:** `gh` CLI must be authenticated.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Prerequisites

```bash
gh auth status
```

If not authenticated, stop and tell the user to run `gh auth login`.

Detect repo info:

```bash
OWNER=$(gh repo view --json owner --jq '.owner.login')
REPO=$(gh repo view --json name --jq '.name')
```

### Step 2: Create or link project

First, check for existing projects:

```bash
gh project list --owner <OWNER> --format json
```

If projects exist, list them numbered and ask the user:

> Found existing projects:
> 1. Project-Name (#3)
> 2. Other-Project (#7)
> 3. Create a new project
>
> Which project should Helm use?

If the user picks an existing project, use its number and skip project creation. Proceed to Step 3.

If the user picks "Create new" or no projects exist:

```bash
gh project create --title "<REPO>" --owner <OWNER> --format json
```

Parse JSON output to get the project `number`. Then link to the repo:

```bash
gh project link <NUMBER> --owner <OWNER> --repo <OWNER>/<REPO>
```

### Step 3: Get the Status field ID

```bash
gh project field-list <NUMBER> --owner <OWNER> --format json
```

Parse to find the field where `name == "Status"` and extract its `id`.

### Step 4: Configure Status columns

Replace default columns (Todo/In Progress/Done) with Helm phases via GraphQL:

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

Parse the response to get the option ID for each column name.

### Step 5: Get the Project Node ID

Detect owner type first:

```bash
gh api users/<OWNER> --jq '.type'
```

Returns `"User"` or `"Organization"`. Use the matching query:

**For User:**
```bash
gh api graphql -f query='
  query {
    user(login: "<OWNER>") {
      projectV2(number: <NUMBER>) {
        id
      }
    }
  }'
```

**For Organization:**
```bash
gh api graphql -f query='
  query {
    organization(login: "<OWNER>") {
      projectV2(number: <NUMBER>) {
        id
      }
    }
  }'
```

### Step 6: Create directory structure and config

```bash
mkdir -p _helm/knowledge _helm/scratch/plans _helm/scratch/briefs
```

Write `_helm/config.yaml` with all collected values:

```yaml
worktree:
  branch-template: "{slug}"
  path-template: "../{slug}"

github:
  owner: "<OWNER>"
  repo: "<REPO>"
  project-number: <NUMBER>
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

Add `_helm/scratch/` to `.gitignore` if not already present.

### Step 8: Ask for branch template

Ask the user:

> Branch naming template? Examples: `hanf/{parent-slug}/{slug}` (team repo), `{slug}` (solo repo)

Update `worktree.branch-template` in `_helm/config.yaml` with the user's answer.

### Step 9: Report

```
Helm initialized:
  Project: <REPO> (#<NUMBER>)
  Board: https://github.com/users/<OWNER>/projects/<NUMBER>
  Config: _helm/config.yaml

Switch to Board layout in GitHub (click layout dropdown) to see kanban columns.
Run helm-add to create your first task.
```
