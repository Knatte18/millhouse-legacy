---
name: feedback
description: Report bugs, suggestions, or corrections to the millhouse repo from any repo. Invoke as /feedback "your message here".
---

# Feedback Skill

Report bugs, suggestions, or corrections to the millhouse repo — from any repo, without needing millhouse checked out locally.

## Usage

```
/feedback "helm-go leste ikke CONSTRAINTS.md"
/feedback "codeguide genererer feil path for nested modules"
```

The argument is a free-text message describing the issue, bug, or suggestion.

## Instructions

When the user invokes `/feedback`, follow these steps exactly:

### 1. Collect context automatically

Run these commands to gather context for the issue body:

```bash
git remote get-url origin 2>/dev/null || echo "(no git remote)"
git branch --show-current 2>/dev/null || echo "(no branch)"
date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date
```

### 2. Try creating a GitHub issue with `gh`

Run:

```bash
gh issue create --repo Knatte18/millhouse --label feedback \
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

### 3. If `gh` is not installed or the command fails

Fall back to opening a pre-filled GitHub issue URL in the browser:

```bash
# Detect platform and open URL
# Windows:
start "https://github.com/Knatte18/millhouse/issues/new?labels=feedback&title=<url-encoded title>&body=<url-encoded body>"
# macOS:
open "https://github.com/Knatte18/millhouse/issues/new?labels=feedback&title=<url-encoded title>&body=<url-encoded body>"
# Linux:
xdg-open "https://github.com/Knatte18/millhouse/issues/new?labels=feedback&title=<url-encoded title>&body=<url-encoded body>"
```

URL-encode the title and body. Detect the platform from the environment.

### 4. Confirm to the user

Tell the user whether the issue was created (with a link) or whether the browser was opened as fallback.
