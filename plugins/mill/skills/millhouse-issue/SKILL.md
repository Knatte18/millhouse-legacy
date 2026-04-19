---
name: millhouse-issue
description: Report bugs, suggestions, or corrections to the millhouse repo from any repo. Invoke as /millhouse-issue "your message here".
---

# millhouse-issue

Report bugs, suggestions, or corrections to the millhouse repo — from any repo, without needing millhouse checked out locally.

## Usage

```
/millhouse-issue "mill-go leste ikke CONSTRAINTS.md"
/millhouse-issue "codeguide genererer feil path for nested modules"
```

The argument is a free-text message describing the issue, bug, or suggestion.

## Instructions

When the user invokes `/millhouse-issue`, follow these steps exactly:

### 1. Collect context automatically

Run these commands to gather context for the issue body:

```bash
git remote get-url origin 2>/dev/null || echo "(no git remote)"
git branch --show-current 2>/dev/null || echo "(no branch)"
date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date
```

### 2. Auto-pick label

Determine the label from the **user's message** (case-insensitive). If it contains any of these words: `fix`, `crash`, `broken`, `error`, `fail`, `wrong`, `bug` — the label is `bug`. Otherwise the label is `enhancement`.

### 3. Try creating a GitHub issue with `gh`

Run:

```bash
gh issue create --repo Knatte18/millhouse-legacy --label "<auto-picked label>" \
  --title "<user's message>" \
  --body "$(cat <<'BODY'
## Feedback

<user's message>

## Context

- **Source repo:** <origin URL>
- **Branch:** <current branch>
- **Timestamp:** <UTC timestamp>
BODY
)"
```

Replace placeholders with the actual values collected in step 1.

### 4. If `gh` is not installed or the command fails

Fall back to opening a pre-filled GitHub issue URL in the browser:

```bash
# Detect platform and open URL
# Windows:
start "https://github.com/Knatte18/millhouse-legacy/issues/new?labels=<auto-picked label>&title=<url-encoded title>&body=<url-encoded body>"
# macOS:
open "https://github.com/Knatte18/millhouse-legacy/issues/new?labels=<auto-picked label>&title=<url-encoded title>&body=<url-encoded body>"
# Linux:
xdg-open "https://github.com/Knatte18/millhouse-legacy/issues/new?labels=<auto-picked label>&title=<url-encoded title>&body=<url-encoded body>"
```

URL-encode the title, body, and label name. Detect the platform from the environment.

Note: GitHub's browser URL may not reliably pre-fill labels. Tell the user to verify the label was applied after the page opens.

### 5. Confirm to the user

Tell the user whether the issue was created (with a link) or whether the browser was opened as fallback.
