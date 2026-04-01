# Coherence Audits & Quality Dimensions

## Coherence Audits

### What They Do

A coherence audit checks whether new code is consistent with the rest of the codebase. It catches problems that no single task could see: duplicate utilities, naming drift, security patterns missing on new endpoints, convention inconsistencies.

### When They Run

During `helm-merge`, after merging parent into the worktree branch and before merging back to parent:

1. Take the diff between parent HEAD and current worktree HEAD.
2. Select relevant quality dimensions based on what the diff touches.
3. For each dimension: spawn an Agent that reads the diff AND the full codebase.
4. Agent looks for cross-codebase inconsistencies introduced by the diff.
5. Report BLOCKING vs INFO findings.
6. BLOCKING issues must be fixed before merge proceeds.

### Dimension Selection

Based on changed files (same as Autoboard's checkpoint mode):

**Always included:**
- `code-organization` — file structure, module boundaries, dead code
- `dry-code-reuse` — duplication, shared abstractions
- `error-handling` — consistent error patterns
- `security` — auth, validation, injection prevention
- `test-quality` — coverage, test types, critical path testing

**Included if diff touches that area:**

| Trigger | Dimension |
|---------|-----------|
| API routes (`**/api/**`, `**/routes/**`) | `api-design` |
| Frontend files (`*.tsx`, `*.jsx`, `**/components/**`) | `frontend-quality` |
| Type definitions (`**/types/**`, `**/schema/**`) | `type-safety` |
| Schema/migrations (`**/migrations/**`, `**/prisma/**`) | `data-modeling` |
| Server/query code (`**/queries/**`, `**/db/**`) | `performance` |
| Request handling (`**/middleware/**`) | `observability` |
| Config files (`**/.env*`, `**/config/**`) | `config-management` |

### Audit Agent Prompt

Use `haiku` model for dimension agents (configured in `_helm/config.yaml` under `models.audit`). They do breadth scanning, not deep reasoning.

Each dimension agent receives:
- The dimension's checklist (Principle, Criteria, Common Violations)
- The diff (`git diff <checkpoint>..HEAD`)
- Project context (tech stack, key directories)
- Instruction: find issues in the diff that are inconsistent with the full codebase

The agent greps and reads the full codebase to cross-reference — it's not limited to the diff.

### Blocking Threshold

BLOCKING for issues that:
- Break the build or existing tests
- Will confuse or mislead future AI sessions (dead code, naming drift, duplicated patterns)
- Will hurt end users (security gaps, missing error handling, performance issues)

INFO for truly cosmetic issues that don't affect correctness or navigability.

### Fixing Blocking Issues

If BLOCKING issues are found:
1. CC fixes them in the worktree (autonomous, same as helm-go execution).
2. Re-runs verification.
3. Re-runs coherence audit on the updated diff.
4. Max 3 fix-audit cycles. If unresolved, escalate to user.

---

## Quality Dimensions

### Overview

Configurable per-repo quality standards. Each dimension has:
- **Principle** — one-sentence rule
- **Criteria** — specific checkable items
- **Common Violations** — what to flag
- **Language-Specific Guidance** — examples per language/framework

### Relationship to Existing Skills

The `code-quality` skill (from the `code` plugin) remains always-on for general coding. Quality dimensions are an *additional* layer used at:
- **Review time** — plan-reviewer and code-reviewer check against active dimensions
- **Audit time** — coherence audits use dimension checklists

Dimensions are selective (loaded per-diff), skills are always-on. They coexist.

### Configuration

Per-repo config at `_helm/dimensions.json`:

```json
{
  "active": [
    "security",
    "error-handling",
    "test-quality",
    "api-design",
    "code-organization"
  ],
  "overrides": {
    "test-quality": {
      "min-coverage": "80%"
    }
  }
}
```

Dimensions not listed are skipped during reviews and audits.

### Shipping Defaults

Ship default dimension templates with the Helm plugin (same as Autoboard's `standards/dimensions/` directory). Repos can override or extend.

### Dimension Templates

To be defined during implementation. Initial set based on Autoboard's 13 dimensions:

1. `security` — input validation, auth, secrets, injection prevention
2. `error-handling` — error types, recovery, logging, failure paths
3. `type-safety` — type coverage, boundary validation, schema contracts
4. `dry-code-reuse` — duplication, shared abstractions, single source of truth
5. `test-quality` — coverage, test types, critical path testing, TDD patterns
6. `config-management` — environment config, feature flags, secrets separation
7. `frontend-quality` — component reuse, state management, accessibility
8. `data-modeling` — schema design, indexes, migrations, query patterns
9. `api-design` — endpoint consistency, validation, versioning, error responses
10. `observability` — logging, metrics, tracing, alerting
11. `performance` — bottlenecks, N+1 queries, unbounded operations, caching
12. `code-organization` — file structure, module boundaries, dead code, file sizes
13. `developer-infrastructure` — CI/CD, lint enforcement, build reliability
