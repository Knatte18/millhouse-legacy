---
name: git-issue
description: "Create a GitHub issue on the current repo"
argument-hint: "<title>"
---

# Create GitHub Issue

Create a GitHub issue on the repo you're currently working in.

## Usage

```
/issue "Fix login redirect loop"
/issue "Add rate limiting to API endpoints"
```

The argument is the issue title (required).

## Instructions

When the user invokes `/issue`, follow these steps exactly:

### 1. Validate title

If no argument was provided, tell the user:

```
Usage: /issue "Issue title here"
```

Stop — do not proceed without a title.

### 2. Detect repository

Run:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

If that fails, fall back to parsing the remote URL:

```bash
git remote get-url origin
```

Parsing rules for the fallback:
- `https://github.com/owner/repo.git` → strip `https://github.com/` prefix and `.git` suffix
- `git@github.com:owner/repo.git` → strip `git@github.com:` prefix and `.git` suffix
- If no `.git` suffix, strip only the prefix

Result: `owner/repo` (e.g. `Knatte18/millhouse`).

If both methods fail, stop and tell the user: "Could not detect the repository. Are you in a git repo with a GitHub remote?"

### 3. Fetch labels and prompt

Run:

```bash
gh label list --repo <owner/repo> --json name -q '.[].name'
```

- If labels are found: present up to 4 labels as `AskUserQuestion` with `multiSelect: true`. The user can select multiple labels, or use the built-in "Other" option to type comma-separated label names manually.
- If the command fails or returns no labels: skip this step entirely.

### 4. Ask for body (optional)

Ask the user for an optional issue body via `AskUserQuestion`. Present two options:

- **No body** — create the issue with title and labels only.
- **Other** — user types the body text.

If the user skips or provides empty text, omit the `--body` flag.

### 5. Create the issue

Run `gh issue create` with heredoc quoting for safe handling of quotes and special characters:

```bash
gh issue create --repo <owner/repo> \
  --title "$(cat <<'TITLE'
<title text>
TITLE
)" \
  --body "$(cat <<'BODY'
<body text>
BODY
)" \
  --label "<label1>" --label "<label2>"
```

- Omit `--body` entirely if no body was provided.
- Omit all `--label` flags if no labels were selected.
- If only a title: `gh issue create --repo <owner/repo> --title "<title>"` (simple form is fine when no special characters are expected, but prefer heredoc if the title contains quotes).

### 6. Fallback to browser

If `gh` is not installed or the `gh issue create` command fails, fall back to opening a pre-filled GitHub issue URL in the browser:

```bash
# Windows:
start "https://github.com/<owner/repo>/issues/new?title=<url-encoded-title>&body=<url-encoded-body>&labels=<url-encoded-labels>"
# macOS:
open "https://github.com/<owner/repo>/issues/new?title=<url-encoded-title>&body=<url-encoded-body>&labels=<url-encoded-labels>"
# Linux:
xdg-open "https://github.com/<owner/repo>/issues/new?title=<url-encoded-title>&body=<url-encoded-body>&labels=<url-encoded-labels>"
```

URL-encode title, body, and label names. Separate multiple labels with commas in the `labels` parameter. Detect the platform from the environment.

### 7. Confirm

Tell the user whether the issue was created (with the issue URL from `gh` output) or whether the browser was opened as fallback.
