---
name: git-pr
description: "Create a GitHub Pull Request from the current branch"
argument-hint: "[base-branch]"
---

# Create Pull Request

Create a PR from the current branch to a base branch. Auto-generates title and body from commit history.

## Usage

```
/git-pr
/git-pr develop
```

No argument: base branch is resolved automatically. With argument: use the given branch as base.

## Instructions

When the user invokes `/git-pr`, follow these steps exactly:

### 1. Validate branch

Get the current branch:

```bash
git branch --show-current
```

If on `main` or `master`: stop and tell the user "You're on main — switch to a feature branch first."

### 2. Determine base branch

Resolve the base branch in this order:

1. **Argument** — if the user provided one (e.g. `/git-pr develop`), use it.
2. **`_git/config.yaml`** — if the file exists and contains a `parent-branch` key, use its value. If the file doesn't exist, skip silently.
3. **Default** — `main`.

Verify the base branch exists on the remote:

```bash
git ls-remote --heads origin <base>
```

If it doesn't exist, stop and tell the user: "Base branch `<base>` not found on remote."

### 3. Detect in-progress merge

Check for an in-progress merge:

```bash
git status
```

If a merge is in progress:

1. Read `.git/MERGE_HEAD` and `.git/MERGE_MSG` to identify what merge is in progress.
2. Report to the user: "A merge is in progress: `<MERGE_MSG summary>`. Continue?"
3. Wait for explicit confirmation before running `git merge --continue`.
4. If confirmed: complete the merge, then run `git fetch origin <base>` (to ensure remote ref is current) and continue to step 5 (verify).
5. If denied: stop.

If no merge is in progress: proceed to step 4.

### 4. Fetch and merge base

```bash
git fetch origin <base>
git merge origin/<base>
```

If merge conflicts occur:
- Help the user resolve each conflict.
- After resolution, stop and tell the user: "Conflicts resolved. Run `/git-pr` again to continue."

If already up to date or merge succeeds cleanly: continue.

### 5. Verify

Detect the project language (see `@conduct:workflow` Language Detection) and run the build/test step from the matching `{lang}-build` skill.

If no verify command is found, emit a visible warning:

> **No build/test command configured — proceeding without verification.**

Do not silently skip.

### 6. Push

```bash
git push --set-upstream origin <branch>
```

Never force-push. Never use `--no-verify`.

### 7. Check for existing PR

```bash
gh pr view --json url -q .url
```

If a PR already exists for this branch: report the URL and stop. Do not create a duplicate.

If `gh` is not installed: tell the user "Skipping existing-PR check — `gh` not available." Proceed to step 8.

### 8. Detect repository

If `gh` was already determined to be unavailable in step 7, skip straight to parsing the remote URL below.

Otherwise, run:

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

### 9. Generate PR content

Read the commit log for the branch:

```bash
git log origin/<base>..HEAD --oneline
```

**Filter noise:** Skip commits whose messages contain any of: `wip`, `fixup`, `typo`, `fmt`, `format`, `merge branch` (case-insensitive). These are housekeeping commits that don't belong in the PR description.

**Generate title:** A concise summary of the overall change. If only one meaningful commit, use its message. If multiple, write a summary that captures the intent.

**Generate body:** A markdown summary of the meaningful changes. Group related commits, explain the "why" not the "what". Use bullet points. Keep it concise — a few sentences, not a wall of text.

### 10. Create the PR

```bash
gh pr create --base <base> --head <branch> \
  --title "<title>" \
  --body "$(cat <<'BODY'
<body text>
BODY
)"
```

### 11. Fallback to browser

If `gh` is not installed or the `gh pr create` command fails, fall back to opening a pre-filled GitHub PR URL in the browser:

```bash
# Windows:
start "https://github.com/<owner/repo>/compare/<base>...<branch>?expand=1&title=<url-encoded-title>&body=<url-encoded-body>"
# macOS:
open "https://github.com/<owner/repo>/compare/<base>...<branch>?expand=1&title=<url-encoded-title>&body=<url-encoded-body>"
# Linux:
xdg-open "https://github.com/<owner/repo>/compare/<base>...<branch>?expand=1&title=<url-encoded-title>&body=<url-encoded-body>"
```

URL-encode title and body. Detect the platform from the environment.

### 12. Report

Tell the user the PR URL from `gh` output, or that the browser was opened as fallback.
