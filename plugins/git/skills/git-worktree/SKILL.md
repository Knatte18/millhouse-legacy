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

**If no argument:** ask the user via AskUserQuestion with two options:

- "Current branch (`<current_branch>`)" (Recommended) — check out the same branch in a new worktree
- "New branch" — user types a new branch name

If the user selects "New branch" or types a custom value via the built-in Other option, use their typed value as the branch name.

### 3. Derive slug and default directory name

Take the last `/`-separated segment of the branch name. If no `/` in the branch name, use the full name. Lowercase, replace spaces with hyphens, remove special characters, truncate to max 20 characters.

Examples:
- `feature/add-oauth` → `add-oauth`
- `main` → `main`
- `hanf/feature/long-branch-name-here` → `long-branch-name-here`

Default directory name: `<repo-name>-wt-<slug>`

### 4. Ask for directory name

Ask the user via AskUserQuestion with two options:

- "`<repo-name>-wt-<slug>`" (Recommended) — uses the derived default name
- "Custom name" — user types their own directory name

If the user selects "Custom name" or types via the built-in Other option, use their typed value.

### 5. Create worktree

Resolve the path as `../<chosen-name>` relative to the repo root.

Check if the branch already exists:

```bash
git rev-parse --verify <branch> 2>/dev/null
```

- **Branch exists:** `git worktree add <path> <branch>`
- **Branch does not exist:** `git worktree add <path> -b <branch> HEAD`

If the command fails, report the error and stop.

### 6. Symlink environment files

From the repo root directory (`git rev-parse --show-toplevel`), symlink all `.env*` files to the worktree:

```bash
for f in .env*; do [ -f "$f" ] && ln -sf "$(pwd)/$f" "<worktree-path>/$f"; done
```

Skip silently if no `.env*` files exist in the repo root.

### 7. Create .vscode/settings.json

Create `.vscode/settings.json` in the worktree with a random title bar color and window title:

```json
{
  "workbench.colorCustomizations": {
    "titleBar.activeBackground": "<color>",
    "titleBar.activeForeground": "#ffffff"
  },
  "window.title": "${rootName}"
}
```

**Color selection:** Pick from this palette (all readable with white text):
`#2d7d46`, `#7d2d6b`, `#2d4f7d`, `#7d5c2d`, `#6b2d2d`, `#2d6b6b`, `#4a2d7d`, `#7d462d`

**Avoid duplicates:** Run `git worktree list --porcelain`, parse each `worktree:` path, read `.vscode/settings.json` if present, extract `workbench.colorCustomizations.titleBar.activeBackground`. If the file is missing or the key is absent, skip that worktree. Pick a color not already in use. If all colors are taken, cycle back to the first.

### 8. Open VS Code

Use `code.cmd` (not `code` — the wrapper is broken on Node 24+):

```bash
code.cmd "$(cd <path> && pwd -W)"
```

If `code.cmd` is not in PATH, use the full path: `"/c/Users/henri/AppData/Local/Programs/Microsoft VS Code/bin/code.cmd"`.

### 9. Report

Tell the user:

```
Worktree created at <path> on branch <branch>.
```
