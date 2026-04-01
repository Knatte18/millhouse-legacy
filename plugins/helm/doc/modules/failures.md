# Failure Classification & Escalation

## Overview

When something fails during `helm-go`, classify the failure before deciding how to respond. Inspired by Autoboard's four-category failure system, simplified for single-threaded execution.

## Classification

### 1. Permission / Config Error

**Signals:** "permission denied", "module not found", missing API key, env var undefined.

**Action:** Notify user immediately. Do NOT retry — retrying with the same config hits the same error.

**Notification:**
```
[helm] BLOCKED: Config error
Missing GOOGLE_CLIENT_ID in .env
Worktree: feature/auth-oauth
```

### 2. Code Error

**Signals:** Test failure, type error, build failure where the cause is in code written by this task.

**Action:** Diagnose → fix → retry. Max 3 retries per step.

**Diagnosis before retry:** Read the error output. Identify what went wrong. Adjust the approach. Each retry must be meaningfully different from the previous attempt — if you can't articulate what you're changing, escalate instead of retrying blindly.

### 3. Upstream Dependency Error

**Signals:** Import from a file that doesn't exist yet, API endpoint not available, dependency on another worktree's work that hasn't merged.

**Action:** Block the task. Update status file. Notify user.

```
[helm] BLOCKED: Upstream dependency
Step 3 imports from src/auth/session.ts which doesn't exist.
This file is expected from feature/auth (parent worktree).
Worktree: feature/auth-oauth
```

Do NOT retry — the dependency must be resolved first (parent merges, or plan is revised).

### 4. Review Escalation

**Signals:** Code reviewer has unresolved BLOCKING issues after 3 rounds. The implementing agent and reviewer agent disagree.

**Action:** Notify user with both sides:

```
[helm] NEEDS INPUT: Review dispute
Code reviewer flagged: "Auth middleware bypassed for admin routes"
Implementing agent's position: "Design doc specifies admin routes are unprotected"

Review in: feature/auth-oauth
Issue: #57
```

User resolves by:
- Siding with reviewer (CC fixes)
- Siding with implementer (CC proceeds)
- Providing a different resolution

## Retry Budget

- **Per step:** max 3 retries for code errors
- **Per review:** max 3 rounds for plan review and code review
- **Per coherence audit:** max 3 fix-audit cycles

After exhausting retries, always escalate to user. Never silently skip or proceed with known issues.

## Post-Failure State

On any failure that blocks progress:
1. Update `_helm/scratch/status.md` with `blocked: true` and `blocked_reason:`
2. Send notification (Slack + toast)
3. Update GitHub issue with a comment describing the blocker
4. Move kanban card to **Blocked**
5. Preserve all state — do not clean up, do not rollback automatically

The user investigates in the worktree's VS Code window and either fixes manually or provides guidance for CC to retry.
