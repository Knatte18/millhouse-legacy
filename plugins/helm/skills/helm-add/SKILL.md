---
name: helm-add
description: Create a new task on the GitHub Projects board.
---

# helm-add

One-shot. Create a GitHub issue and add it to the project board.

---

## Usage

```
helm-add <title>: <body>
helm-add <title>
```

Text before the first colon is the title. Text after is the body. No colon means title only.

## Steps

### Step 1: Read config

Read `_helm/config.yaml`. Extract `github.owner`, `github.repo`, and `github.project-number`.

If `_helm/config.yaml` does not exist, stop and tell the user to run `helm-setup` first.

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) → issue title
- Right side (trimmed) → issue body (may be empty)

### Step 3: Create issue

```bash
gh issue create --title "<title>" --body "<body>" --repo <owner>/<repo>
```

Parse the output to get the issue URL.

### Step 4: Add to project board

```bash
gh project item-add <project-number> --owner <owner> --url <issue-url> --format json
```

Parse the output to get the item ID.

### Step 5: Set status to Backlog

Read `github.project-node-id`, `github.status-field-id`, and `github.columns.backlog` from `_helm/config.yaml`.

```bash
gh project item-edit --id <item-id> --project-id <project-node-id> --field-id <status-field-id> --single-select-option-id <backlog-option-id>
```

### Step 6: Report

```
Added: #<number> <title>
```
