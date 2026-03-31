# Codeguide Integration

## Overview

Codeguide provides navigation-first documentation for AI-assisted codebases. It has four skills with distinct roles:

| Skill | Purpose | Reads source? |
|-------|---------|---------------|
| `codeguide-generate` | Create docs for undocumented source files | Yes |
| `codeguide-update` | Update docs for recently changed files (git diff) | Yes |
| `codeguide-maintain` | Audit and fix existing docs against guide and local rules | Yes (full mode) or No (--structure) |
| `review-navigation` | Review navigation failures and propose routing improvements | No |

Key insight: codeguide docs are **navigation aids**, not API docs. They describe *what and why* in plain language, with routing hints so the reader knows where to look. No signatures, no code-derived values, no line-by-line walkthroughs.

## Integration Points

### helm-start (discussion phase)

**Read codeguide for navigation.** Before exploring the codebase:

1. Read `_codeguide/Overview.md` — get the module table and routing hints.
2. Use the Overview to identify which module docs are relevant to the task.
3. Read those module docs — they describe capabilities, relationships, and negative space ("when NOT to use this").
4. Navigate to source files via the `## Source` section in each doc (relative paths to actual files).

This replaces blind searching. The Overview routes you to the right module, the module doc tells you what's there, the Source section links to the code.

### helm-go (explore phase)

**Follow plan's `Explore:` targets using codeguide routing.** Same pattern as helm-start:

1. Read Overview → find relevant module docs → read them → follow Source links to code.
2. For `Explore:` targets like "How existing auth middleware validates tokens" — the Overview routing hints tell you which module handles auth, the module doc confirms what it does, and the Source section points to the file.

### helm-go (after implementation, before commit)

**Run `codeguide-update` on the diff.** This is the lightweight skill designed for commit-time use:

- Default scope: current git diff (staged + unstaged) — exactly what's about to be committed.
- For each changed source file: finds the corresponding doc, checks if it's stale, updates if needed.
- Creates docs for new files that don't have one yet.
- Flags orphaned docs (source deleted but doc remains) without deleting them.
- Updates Overview routing tables if new docs were added.

Fast and non-intrusive. Only touches docs for files in scope.

### helm-merge (after merge)

**Run `codeguide-update` on the merge diff.** Same skill, broader scope:

- Scope: diff between parent HEAD and merged worktree HEAD.
- Catches docs that need updating due to changes from the parent branch merging in.
- Also catches cross-file impacts (file A changed behavior that file B's doc describes).

Do NOT run `codeguide-maintain` here — `update` is sufficient. `maintain` is heavy and reserved for guide/rule changes (see below).

### helm-commit (ad-hoc commits)

**Run `codeguide-update`** with default scope (current diff). Same as helm-go's post-implementation call.

## When to Use Each Skill

| Situation | Skill |
|-----------|-------|
| New repo, no docs at all | `codeguide-setup` then `codeguide-generate` |
| Added new source files | `codeguide-generate` (scoped to new files/module) |
| Changed existing source files | `codeguide-update` (default: git diff) |
| Updated DocumentationGuide or local-rules | `codeguide-maintain --structure` (the only routine use of maintain) |
| Updated cgexclude.md | `codeguide-maintain --structure` |
| Full audit (rare, manual) | `codeguide-maintain` (full mode — very heavy, user-initiated only) |
| CC keeps navigating to wrong files | `review-navigation` (reads failure log, proposes routing fixes) |

## Conditional

All codeguide integration is conditional on `_codeguide/Overview.md` existing in the repo. If it doesn't exist, all codeguide calls are skipped silently. Helm does not auto-generate codeguide docs — the user runs `codeguide-setup` + `codeguide-generate` if they want it.

## Navigation Pattern

The codeguide routing pattern used throughout Helm:

```
Overview.md (module table + routing hints)
    → Module doc (capabilities, relationships, negative space)
        → ## Source (relative paths to actual source files)
            → Read the code
```

Never skip steps. Don't go straight to source — the Overview tells you *which* module, the module doc tells you *if* it's relevant, and the Source section tells you *where*.
