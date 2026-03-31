# Reviews

## Plan Review (during helm-start, interactive)

1. User and CC discuss the approach.
2. CC writes plan.
3. CC spawns `plan-reviewer` Agent with the plan and relevant codebase context.
4. CC evaluates feedback via receiving-review protocol (see below).
5. CC updates plan with accepted changes.
6. Repeat: spawn reviewer again with updated plan. Max 3 rounds.
7. User sees the final result and approves.
8. Plan is locked (`approved: true` in frontmatter).

Plan review happens exclusively during `helm-start`. `helm-go` requires an already-approved plan and never runs a discuss or review phase.

## Code Review (during helm-go, autonomous)

1. CC implements all steps.
2. CC runs full verification (lint, type-check, build, test).
3. CC spawns `code-reviewer` Agent with:
   - The full diff (`git diff`)
   - The approved plan
   - Codeguide Overview (for utility duplication checking)
   - Knowledge from prior tasks in this worktree
4. CC evaluates reviewer feedback via receiving-review protocol.
5. CC fixes accepted issues, re-runs full verification, re-submits to reviewer.
6. Max 3 rounds.
7. If unresolved blocking issues after 3 rounds: escalate to user (see [notifications.md](notifications.md)).

The code reviewer is a **separate Agent call** — it has no shared context with the implementing agent. It receives only the diff, plan, and quality standards. This enforces Principle #1: never let the builder inspect their own work.

## Receiving-Review Protocol

Adopted from Autoboard. Implemented as a standalone skill file at `plugins/helm/skills/helm-receiving-review/SKILL.md`.

**MANDATORY:** This skill must be invoked via the Skill tool BEFORE the agent reads any reviewer findings — during both plan review and code review. Loading it after reading findings is useless; the agent has already formed rationalizations by then. The skill is a forcing function that loads the decision tree into context before evaluation begins.

### Core Rule

Default: **fix everything.** The only valid escape is proven harm.

An agent can fix a DRY violation in 30 seconds. The cost of completeness is near-zero. The cost of leaving issues is compounding — every unfixed finding is a pattern the next task copies.

### Decision Tree

For each finding:

```
VERIFY: Is the finding factually accurate?
  → NO → PUSH BACK with evidence (cite actual code)
  → YES or UNCERTAIN → continue

HARM CHECK: Would the fix cause demonstrable harm?
  a. Break existing functionality? → PUSH BACK (cite what breaks)
  b. Conflict with a documented design decision? → PUSH BACK (cite the doc)
  c. Destabilize code outside this task's scope? → PUSH BACK (cite the risk)
  → None of the above → FIX IT
```

### Forbidden Dismissals

These rationalizations are never valid:

- "Low risk" / "low impact"
- "Technically works" / "not build-breaking"
- "Out of scope for this task"
- "Pre-existing issue"
- "Won't change during this project"
- "Cosmetic / style preference"
- "Future task will handle this"

### Legitimate Pushback

Pushback is valid only when:

1. **Factually wrong** — cite the actual code that disproves the finding
2. **Fix breaks something** — identify what breaks
3. **Conflicts with design doc** — cite the document and passage
4. **Destabilizes other work** — cite what is affected and why

## Agent Definitions

### Plan Reviewer

*Role: You are an independent plan reviewer. Evaluate the submitted implementation plan for production readiness before any code is written. Be thorough, critical, and constructive.*

Use `sonnet` model (configured in `_helm/config.yaml` under `models.plan-review`).

Read-only review agent. Evaluates:
- Alignment with task requirements
- Completeness — missing steps, unaddressed requirements
- Sequencing — are steps in the right order?
- Edge cases and risks
- Over-engineering
- Codebase consistency — follows existing patterns?
- Test coverage — key test scenarios cover error paths, not just happy paths?
- Explore targets — purpose-driven, not generic?

Output: BLOCKING issues (must fix) and NITs (nice-to-have). Overall APPROVE or REQUEST CHANGES.

### Code Reviewer

*Role: You are an independent code reviewer. Evaluate the submitted diff for production readiness. You have no shared context with the implementing agent — you see only the diff, the plan, and the quality standards. Be thorough, critical, and constructive.*

Use `sonnet` model (configured in `_helm/config.yaml` under `models.code-review`).

Read-only review agent. Receives: the diff, the approved plan, and the codeguide Overview (if it exists).

Evaluates:
- Plan alignment — does the code match the plan?
- Correctness — bugs, logic errors?
- Dead code — unused exports, unimported files?
- Test thoroughness (enforce `@code:testing` rules):
  - Happy-path-only tests → BLOCKING. Error paths and edge cases from plan's `Key test scenarios` must be covered.
  - Implementation-mirroring tests (testing internal state instead of observable behavior) → BLOCKING.
  - Shallow assertions (`assert result`, `assert result is not None`) → BLOCKING.
  - TDD-marked steps where diff shows implementation committed without a preceding failing test → BLOCKING.
- **Utility duplication** (BLOCKING): For every new function, helper, or utility in the diff, grep the codebase for existing implementations with similar names or purposes. Use the codeguide Overview to identify which modules to check. If an existing utility covers the same functionality, flag the reimplementation as BLOCKING with a pointer to the existing implementation. Common patterns: math/comparison helpers, string formatting, validation logic, error handling wrappers, API client utilities.
- **Pattern consistency**: Check that new code follows the same patterns as existing code in the same area — naming conventions, error handling style, authentication patterns on endpoints.
- Codebase consistency — does the code follow existing patterns?

Output: findings with BLOCKING/NIT severity. Overall APPROVE or REQUEST CHANGES.
