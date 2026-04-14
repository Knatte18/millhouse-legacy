---
name: git-clone
description: "Clone a repo as a bare-repo hub with worktrees"
argument-hint: "<url> [--linear]"
---

# Clone Git Repository

Clone a repo as a bare-repo hub with worktrees (default), or as a standard clone (`--linear`).

## Usage

```
/git-clone https://github.com/user/repo.git          (hub — default)
/git-clone https://github.com/user/repo.git --linear  (standard clone)
/git-clone                                             (detect — inside existing repo)
```

## Hub Structure

```text
<name>/
├── .bare/           ← bare git database
├── .git             ← file: "gitdir: ./.bare"
├── main/            ← worktree for default branch
└── (future worktrees as siblings)
```

## Instructions

When the user invokes `/git-clone`, follow these steps exactly.

### 1. Parse arguments

Extract the URL (if present) and flags from the arguments.

- `--linear` flag → use the **Linear flow** (section below).
- No URL → use the **No-URL flow** (section below).
- URL without `--linear` → use the **Hub flow** (below).

### 2. Hub flow

**Steps are order-dependent — do not reorder.**

#### 2.1. Derive repo name

Take the last path segment of the URL and strip any `.git` suffix.

Examples:
- `https://github.com/user/my-repo.git` → `my-repo`
- `git@github.com:user/my-repo.git` → `my-repo`
- `https://github.com/user/my-repo` → `my-repo`

#### 2.2. Resolve absolute hub path

```bash
hub_path="$(pwd)/$name"
```

All subsequent commands use `$hub_path`. Do not use relative paths.

#### 2.3. Check target doesn't exist

If `$hub_path` already exists, report the error and stop:

> "Directory `<name>/` already exists. Remove it first or choose a different location."

#### 2.4. Clone bare repo

```bash
git clone --bare <url> "$hub_path/.bare"
```

If the clone fails, report the error and stop.

#### 2.5. Verify bare clone

```bash
git -C "$hub_path/.bare" rev-parse --is-bare-repository
```

Must return `true`. If not, report error and stop. This check must run immediately after the clone, before any operations on the bare repo.

#### 2.6. Configure fetch refspec

Bare clones omit the remote-tracking fetch refspec by default. Without this configuration, `git fetch` inside worktrees won't update remote-tracking branches.

```bash
git -C "$hub_path/.bare" config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
```

#### 2.7. Initial fetch

```bash
git -C "$hub_path/.bare" fetch origin
```

#### 2.8. Write .git redirect file

Write the file `$hub_path/.git` (a plain file, not a directory) with this exact content:

```
gitdir: ./.bare
```

This redirect file is required for all subsequent `git -C "$hub_path"` commands. Steps 2.9–2.10 depend on it.

#### 2.9. Detect default branch

Use this fallback chain:

1. **Primary (local, no network):**
   ```bash
   git -C "$hub_path/.bare" symbolic-ref HEAD 2>/dev/null
   ```
   Strip the `refs/heads/` prefix to get the branch name (e.g. `main`, `master`). If the result is empty after stripping (detached HEAD), fall through to step 2.

2. **Last resort:** Ask the user for the default branch name via `AskUserQuestion`.

#### 2.10. Create main worktree

Bare clones populate `refs/heads/` with all upstream branches. Check whether the default branch exists locally:

```bash
git -C "$hub_path/.bare" show-ref --verify "refs/heads/<default-branch>" 2>/dev/null
```

- **Branch exists locally** (common case):
  ```bash
  git -C "$hub_path" worktree add main <default-branch>
  ```

- **Branch does not exist locally** (unusual — e.g. empty repo or stripped bare clone):
  ```bash
  git -C "$hub_path" worktree add -b <default-branch> main "origin/<default-branch>"
  ```

If the command fails, report the error and stop.

#### 2.11. Create mill-worktree forwarding wrapper

Write `$hub_path/main/_millhouse/mill-worktree.cmd` with the following one-line content:

```batch
@python "%USERPROFILE%\.claude\plugins\cache\millhouse\mill\worktree.py" %*
```

The wrapper delegates to `worktree.py` in the Claude Code plugin cache. A more robust version that picks the latest installed mill version on each invocation can be substituted at a later time; for bootstrap purposes the single-line form is sufficient.

Commit and push the wrapper so it propagates to all worktrees via git:

```bash
git -C "$hub_path/main" add -f _millhouse/mill-worktree.cmd
git -C "$hub_path/main" commit -m "chore: add mill-worktree forwarding wrapper"
git -C "$hub_path/main" push
```

#### 2.12. Report

Tell the user:

```
Hub created at <hub_path>
Main worktree: <hub_path>/main (branch: <default-branch>)
```

### 3. Linear flow

Standard clone — nothing special.

```bash
git clone <url>
```

Report:

```
Cloned to <name>/
```

### 4. No-URL flow (inside existing repo)

When invoked without a URL while inside a git repo.

#### 4.1. Find repo root

```bash
root=$(git rev-parse --show-toplevel)
```

#### 4.2. Detect hub vs regular repo

Check the `.git` entry at the repo root:

```bash
test -f "$root/.git"
```

If `.git` is a **file**: read its content. If the `gitdir:` value points to a path ending in `.bare`, this is a hub worktree. Report:

> "This repo is already a hub."

Stop.

If `.git` is a **directory** (regular repo) or the gitdir doesn't point to `.bare`: continue.

#### 4.3. Get remote URL

```bash
url=$(git remote get-url origin 2>/dev/null)
```

#### 4.4. Report

If URL was found:

> "This repo is not a hub. To convert: delete this repo and run `/git-clone <url>`"

If no remote URL:

> "This repo is not a hub and has no remote. Clone from a URL instead: `/git-clone <url>`"

### Error handling

- **Target directory exists:** abort with clear message (step 2.3)
- **Clone fails:** report git error output (step 2.4)
- **Bare verification fails:** report unexpected state (step 2.5)
- **No default branch detected:** ask user (step 2.9)
- **Worktree add fails:** report git error output (step 2.10)
- **Partial failure cleanup:** if any step after 2.4 fails (hub directory partially created), advise the user: "Hub creation failed. Delete `<hub_path>` before retrying."
