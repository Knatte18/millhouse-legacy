---
name: git-worktree
description: "Create a git worktree and open it in VS Code"
argument-hint: "[branch-name]"
---

# Create Git Worktree

Create a git worktree from VS Code. Simple convenience skill — no Helm, no kanban, no task management.

## Usage

```
/git-worktree feature/my-branch
/git-worktree                     (interactive — asks for branch)
```

## Instructions

When the user invokes `/git-worktree`, follow these steps exactly:

### 1. Detect repo info

```bash
repo_name=$(basename "$(git rev-parse --show-toplevel)")
current_branch=$(git branch --show-current)
```

### 2. Determine branch

**If a branch argument was provided:** use it as the branch name.

**If no argument:** ask the user via AskUserQuestion:

- Question: "What branch name?"
- Default suggestion: current branch name
- Let the user type freely

### 3. Determine worktree directory name

Derive a default slug from the branch name: take the last `/`-separated segment, lowercase, replace spaces with hyphens, remove special characters, max 20 chars. E.g. `feature/add-oauth` -> `add-oauth`.

Default directory name: `<repo-name>-wt-<slug>`

Ask the user via AskUserQuestion:

- Question: "Worktree directory name?"
- Option 1: the default name (Recommended)
- Option 2: "Custom" — user types their own name

### 4. Create worktree

Resolve the path as `../<chosen-name>` relative to the repo root.

Check if the branch already exists:

```bash
git rev-parse --verify <branch> 2>/dev/null
```

- **Branch exists:** `git worktree add <path> <branch>`
- **Branch does not exist:** `git worktree add <path> -b <branch> HEAD`

If the command fails, report the error and stop.

### 5. Open VS Code

Use `code.cmd` (not `code` — the wrapper is broken on Node 24+):

```bash
code.cmd "$(cd <path> && pwd -W)"
```

If `code.cmd` is not in PATH, use the full path: `"/c/Users/henri/AppData/Local/Programs/Microsoft VS Code/bin/code.cmd"`.

### 6. Report

Tell the user:

```
Worktree created at <path> on branch <branch>.
```
