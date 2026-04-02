# Open Questions

## Resolved

### Backlog format
**Decision:** `.kanban.md` is the backlog. Tasks are `###` headings under `##` column headings. The kanban.md VS Code extension renders the board. GitHub sync is on-demand via `helm-sync`.

### Backlog inheritance on merge
**Decision:** Yes. Child worktree's changelog entries propagate to parent on merge (they're tracked and travel with the merge). Knowledge files also propagate via `_helm/knowledge/`.

### Kanban granularity
**Decision:** One board per repo. Sub-tasks within a worktree are checkboxes on the parent issue, not separate board items (unless large enough for their own worktree/issue).

### Dimension templates
**Decision:** Not used. Codebase consistency is handled by code reviewer (with codeguide context) and existing always-on skills. See [coherence.md](coherence.md).

### Python scripts
**Decision:** Dropped. CC reads/writes files directly. No script-based mutations. Format consistency via skill instructions and optional validation hooks.

### Worktree spawning
**Decision:** Always user-initiated. CC never auto-spawns worktrees. Use `helm-start -w`.

### Plan protection
**Decision:** Plans are freely editable during review loop. Locked after approval (`approved: true` in frontmatter). `helm-go` refuses unapproved plans.

### Concurrent merge safety
**Decision:** Lock file on parent branch (`_helm/scratch/merge.lock`). Lock acquisition resolves parent branch to filesystem path via `git worktree list --porcelain`.

### Worktree naming convention
**Decision:** Configurable via `_helm/config.yaml` with `branch-template`. No separate prefix field — the prefix is part of the template string. Examples: `"hanf/{parent-slug}/{slug}"` (team), `"{slug}"` (solo). No distinction between hotfix/feature/experiment — just slugs.

### _helm/ directory structure
**Decision:** Single `_helm/` directory, partially tracked:
```
_helm/
  knowledge/              ← tracked. knowledge entries
  knowledge/decisions.md  ← tracked. architectural decisions register (append-only)
  changelog.md            ← tracked. completed task log
  config.yaml             ← tracked. worktree config + model/notification settings
  scratch/                ← gitignored (entire directory)
    plans/                ← implementation plans
    briefs/               ← handoff documents
    status.md             ← worktree status (updated every step, not just on error)
    test-baseline.md      ← pre-existing test failures (captured before work starts)
    merge.lock            ← merge locking
```

`.gitignore` entry: `_helm/scratch/`

### helm-go is always autonomous
**Decision:** `helm-go` only executes approved plans. It never runs discuss phases or asks clarifying questions. In new worktrees, the user runs `helm-start` (not `helm-go`) to discuss and plan. `helm-go` is called after plan approval.

### Codeguide update ordering
**Decision:** Codeguide-update runs BEFORE commit in helm-go, not after. Sequence: implement → verify → code-review → codeguide-update → commit.

### Dimensions and coherence audits
**Decision:** Not used. Helm relies on existing always-on skills (`code:code-quality`, `code:testing`, `code:linting`) plus a strengthened code reviewer that checks for utility duplication and pattern consistency using codeguide context. See [coherence.md](coherence.md).

### helm-setup skill
**Decision:** Fully specified in kanban.md "Setup" section. Creates `.kanban.md` with Helm columns and `_helm/` directory structure.

### Knowledge file naming
**Decision:** `<worktree-slug>-<timestamp>-<topic>.md`. Worktree-slug prefix prevents collisions on merge.

### Receiving-review as standalone skill
**Decision:** Standalone skill at `plugins/helm/skills/helm-receiving-review/SKILL.md`. Must be invoked via Skill tool BEFORE reading reviewer findings.

### Cross-platform notifications
**Decision:** Windows (BurntToast), macOS (osascript), Linux (notify-send). Detect platform. Specified in notifications.md.

### Notification config location
**Decision:** Per-repo in `_helm/config.yaml` alongside worktree and kanban config. Not global.

### helm-go context budget
**Decision:** No hard limit on step count. Plan reviewer is responsible for flagging oversized plans. If a plan is too large for one context window, the reviewer should suggest splitting into sub-tasks or child worktrees.

### Agent model selection
**Decision:** Different models for different agent roles to balance cost and quality:

| Agent | Model | Rationale |
|-------|-------|-----------|
| `helm-go` (session agent) | opus | Full reasoning needed for implementation |
| Plan reviewer | sonnet | Reasoning for review, but no implementation |
| Code reviewer | sonnet | Same — review, not implementation |
| Explore subagents | haiku | Fast codebase scanning |

Configurable in `_helm/config.yaml`:

```yaml
models:
  session: opus
  plan-review: sonnet
  code-review: sonnet
  explore: haiku
```

## Still Open

### Changelog format
Carry over Taskmill's changelog format? Use `_helm/changelog.md`? Or rely on GitHub issue comments as the changelog? A tracked changelog is useful for commit history and PR descriptions. Lean toward keeping it.

### Format protection for tracked files
`.kanban.md` is the kanban board — a bad write breaks task tracking. Options: (A) validation hook that checks format on commit, (B) rely on kanban.md extension to enforce format. Knowledge files and changelog are lower risk. Needs a decision.
