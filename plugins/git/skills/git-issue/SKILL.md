---
name: git-issue
description: "Create a GitHub issue on the current repo"
argument-hint: "<title>[: <body>]"
---

# Create GitHub Issue

Create a GitHub issue on the repo you're currently working in.

## Usage

```
/git-issue Fix login redirect loop
/git-issue Fix login redirect loop: The redirect happens after OAuth callback
```

The first `:` separates title from body. If no `:` is present, the entire argument is the title and no body is set. Both title and body are trimmed of leading/trailing whitespace.

## Instructions

When the user invokes `/git-issue`, follow these steps exactly:

### 1. Parse argument

Split the argument on the first `:` character.
- Everything before `:` → **title**
- Everything after `:` → **body** (optional)
- No `:` → entire argument is the title, no body

If no argument was provided, tell the user:

```
Usage: /git-issue Title: optional body text
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

**Override: Do NOT use AskUserQuestion for labels.** Present labels as a numbered text list instead.

Run:

```bash
gh label list --repo <owner/repo> --json name -q '.[].name'
```

If labels are found, print them as a numbered list:

```
Labels:
1. bug
2. documentation
3. enhancement
...
```

Then ask the user to type the numbers they want, comma-separated (e.g. `1, 5, 9`). The user can also type `none` or leave blank to skip labels.

If the command fails or returns no labels: skip this step entirely.

### 4. Create the issue

Run `gh issue create`. Use simple quoting for `--title` and heredoc quoting for `--body` (to safely handle quotes, newlines, and special characters):

```bash
gh issue create --repo <owner/repo> \
  --title "<title text>" \
  --body "$(cat <<'BODY'
<body text>
BODY
)" \
  --label "<label1>" --label "<label2>"
```

- Omit `--body` entirely if no body was provided.
- Omit all `--label` flags if no labels were selected.

### 5. Fallback to browser

If `gh` is not installed or the `gh issue create` command fails, fall back to opening a pre-filled GitHub issue URL in the browser:

```bash
# Windows:
start "https://github.com/<owner/repo>/issues/new?title=<url-encoded-title>&body=<url-encoded-body>&labels=<url-encoded-labels>"
# macOS:
open "https://github.com/<owner/repo>/issues/new?title=<url-encoded-title>&body=<url-encoded-body>&labels=<url-encoded-labels>"
# Linux:
xdg-open "https://github.com/<owner/repo>/issues/new?title=<url-encoded-title>&body=<url-encoded-body>&labels=<url-encoded-labels>"
```

URL-encode title, body, and label names. Separate multiple labels with commas in the `labels` parameter. Omit `&labels=` entirely if no labels were selected. Omit `&body=` if no body was provided. Detect the platform from the environment.

Note: GitHub's browser URL may not reliably pre-fill labels. If labels were selected, tell the user to verify and apply labels manually after the page opens.

### 6. Confirm

Tell the user whether the issue was created (with the issue URL from `gh` output) or whether the browser was opened as fallback.
