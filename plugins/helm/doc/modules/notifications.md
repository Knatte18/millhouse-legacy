# Notifications

## When Notifications Fire

A worktree sends a notification when it needs user attention:

| Event | Urgency |
|-------|---------|
| Test failure after 3 retries | High |
| Code reviewer blocks after 3 rounds | High |
| Permission/config error | High — immediate, no retries |
| Coherence audit blocking issues unresolvable | High |
| Merge conflict unresolvable | High |
| All tasks complete | Info |
| Worktree ready to merge | Info |

## Channels

### 1. Slack DM (primary)

CC posts a message to a configured Slack channel or DM describing what is needed.

```
[helm] feature/auth-oauth BLOCKED
Test failure in step 3 "Add callback endpoint" after 3 retries.
Error: Cannot find module '@auth/google'
Worktree: C:\Code\myproject-auth-oauth
```

User sees it on phone/desktop. User responds in the worktree's VS Code window — Slack is notification-only (CC cannot read Slack replies back into a session).

Implementation: Slack MCP server or incoming webhook.

### 2. Desktop Toast (fallback)

Platform-specific local popup:

**Windows (PowerShell):**
```powershell
New-BurntToastNotification -Text "helm: feature/auth-oauth BLOCKED", "Test failure after 3 retries"
```
Requires BurntToast module (`Install-Module -Name BurntToast`).

**macOS:**
```bash
osascript -e 'display notification "Test failure after 3 retries" with title "helm: feature/auth-oauth BLOCKED"'
```

**Linux:**
```bash
notify-send "helm: feature/auth-oauth BLOCKED" "Test failure after 3 retries"
```
Requires `libnotify` (pre-installed on most desktop distros).

Less context than Slack, but works offline from Slack. Detect platform via `uname` or `$OSTYPE`.

### 3. Status file (always — updated continuously, not just on notifications)

`_helm/scratch/status.md` is updated after **every step**, not just on errors. This is the live progress indicator.

```markdown
parent: feature/auth
phase: implementing
issue: #57
current_step: 3
current_step_name: Add callback endpoint
tasks_total: 3
tasks_done: 1
steps_total: 5
steps_done: 2
blocked: false
retries:
  step_3: 1
last_updated: 2026-04-01T14:30:00Z
```

On error, adds:
```markdown
blocked: true
blocked_reason: Test failure in step 3 after 3 retries — Cannot find module '@auth/google'
needs_input: true
```

`helm-status` reads these files to show the dashboard. This is the most reliable channel — always written, no external dependencies.

## Configuration

Notification config lives in `_helm/config.yaml` (per-repo, alongside worktree and kanban config):

```yaml
notifications:
  slack:
    enabled: true
    webhook: "https://hooks.slack.com/services/..."
    channel: "#cc-notifications"
  toast:
    enabled: true
```

Status file is always written regardless of config.

## Design Decisions

- **Slack is notification-only.** CC cannot poll Slack for replies. The interaction happens in VS Code where the CC session is running.
- **Multiple channels fire simultaneously.** Slack + toast + status file all update on the same event. Redundancy is intentional — you might miss one.
- **Info notifications are status-file only.** "All tasks complete" doesn't need a Slack ping. Check `helm-status` when ready.
