# Claude CLI — Known Limits for Long Tool-Use Sessions

Notes and workarounds for drifting-scope quirks when running `claude -p` as a subprocess in `plugins/mill/scripts/millpy/backends/claude.py`. Written after empirical observation on 2026-04-17 during the Gemini-backend / ensemble-pipeline hardening task.

---

## Observed bug: headless tool-use hangs on long sessions

**Symptom:** `claude -p --model sonnet --max-turns N --output-format json --effort max` exits with code 1 after ~11–22 minutes on holistic plan-review or code-review tasks that involve many Read-tool calls. No review file is written; stdout is empty or truncated. The CLI *completes* its work internally but fails to exit cleanly.

**Empirical data (same worktree, same plan, 12-card artifact):**

| max_turns | Wall-clock before crash | Exit code | Review written |
|-----------|------------------------|-----------|----------------|
| 30 | 649 s (~10.8 min) | 1 | no |
| 100 | 1300 s (~21.7 min) | 1 | no |

Doubling `max_turns` doubled the runtime but did not prevent the crash — confirming the hang is **not** a turn-budget issue.

**Upstream references:**

- [anthropics/claude-code #25629 — CLI hangs indefinitely after sending result event in stream-json mode](https://github.com/anthropics/claude-code/issues/25629)
- [anthropics/claude-agent-sdk-python #701 — Agent SDK CLI hangs indefinitely during synthesis after successful tool calls](https://github.com/anthropics/claude-agent-sdk-python/issues/701)
- [anthropics/claude-code #45717 — Bash tool timeout kills Claude Code process (SIGTERM propagation)](https://github.com/anthropics/claude-code/issues/45717)

**Hypothesis:** Claude Code CLI has a process-exit bug where the inner agent finishes successfully but the outer CLI process fails to flush/exit, leading to SIGTERM or indefinite hang after some internal timeout.

---

## Workarounds for mill's reviewer pipeline

### 1. Prefer Agent-tool subagent for large tool-use reviews

Instead of `spawn_reviewer --reviewer-name sonnetmax` (which dispatches via `claude -p` subprocess), use the Claude Agent tool (in-process subagent via the SDK). The subagent runs inside the current orchestrator's session and is not subject to the subprocess-hang bug.

Empirical: a plan-review that failed twice via `claude -p` completed successfully in 248 s (4 min) via Agent-tool subagent.

Tradeoffs:
- Pro: no subprocess hang; structured return.
- Con: requires an orchestrator to invoke the Agent tool; not usable from mill-plan's autonomous flow today (which uses `spawn_reviewer.py`).

### 2. Default Claude worker `max_turns: 500`

In `plugins/mill/scripts/millpy/reviewers/workers.py`, all Claude-provider Worker entries (`haiku`, `sonnet`, `sonnetmax`, `opus`, `opusmax`) declare `max_turns=500`. This gives Sonnet enough turn budget for large holistic tasks without artificially capping at the old 30-turn default. Note: the crash above is not fixed by raising `max_turns`, but the raise eliminates the *easier* failure mode where a legitimate long session runs out of turns and gets killed before it hits the CLI bug.

### 3. Prefer bulk flash ensembles for closed-scope reviews

For plan-review holistic, plan-review per-card, and code-review where the file set is enumerable from `reads:` / `## All Files Touched`: use `g25flash-x3-g25flash` (paid-tier Gemini) with bulk dispatch. This completely bypasses Claude CLI subprocess and avoids the bug class. Reviews complete in 40–80 s with source-file verification inlined via `<FILES_PAYLOAD>`.

Reserved for Claude tool-use: discussion-review (open-scope; reviewer must decide which files to Read).

### 4. Optional: raise `BASH_DEFAULT_TIMEOUT_MS` in `~/.claude/settings.json`

For unrelated bash-tool timeouts (default 120 s), the settings.json env supports `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS`. Does not resolve the tool-use subprocess hang, but helps for long-running sub-commands.

---

## Gemini CLI — tool-use via `--yolo` works

Separate from the Claude subprocess limit, worth noting: **Gemini CLI 0.38.1 supports tool-use in headless mode** via `--yolo` (or `--approval-mode yolo`). Empirical test 2026-04-17:

```bash
echo "Read <file> and write <summary> to <out>. Stdout only DONE." \
  | gemini -p - --model gemini-2.5-flash --yolo
```

Completed in 8 s with Read + Write tool calls and correct output.

Implication: Gemini can act as a tool-use worker or tool-use handler without the SDK migration. Currently `GeminiBackend.dispatch_tool_use` in `plugins/mill/scripts/millpy/backends/gemini.py` raises `NotImplementedError`; implementing it via `gemini -p - --yolo` is a ~30-line change. Not prioritized because bulk-dispatch with `<FILES_PAYLOAD>` inlined is already optimal for mill's structured-review use cases. Tool-use Gemini would only add value for open-scope reviews (discussion-review), and there Claude sonnet is still the quality anchor.

---

## Review-strategy playbook

| Review type | Scope | Recommended dispatch | Backend |
|-------------|-------|----------------------|---------|
| Discussion review | Open (reviewer navigates) | Tool-use | Claude sonnetmax via `claude -p` — bounded to <15 min artifacts to avoid subprocess hang |
| Plan review (holistic) | Closed (`## All Files Touched`) | Bulk | Gemini `g25flash-x3-g25flash` with `<PLAN_CONTENT>` + `<FILES_PAYLOAD>` |
| Plan review (per-card) | Closed (card's `reads:`) | Bulk | Gemini `g25flash-x3-g25flash` |
| Code review | Closed (changed files) | Bulk | Gemini `g25flash-x3-g25flash` |
| Large / suspect-quality review | Any | Agent-tool subagent | Claude (in-process) — only route that bypasses CLI subprocess hang |

---

## Review variance is a feature

Running the same flash ensemble twice on the same artifact produced complementary findings in empirical runs (r5 and r6 on the same 12-card plan). r5 found 1 observation, r6 found 5, with only 1 overlap. The union was substantially stronger than either individually. Do not optimize away variance; use multiple runs where confidence matters.
