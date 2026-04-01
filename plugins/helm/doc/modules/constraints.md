# Constraints

## What Constraints Are

Constraints are repo-specific hard invariants that must never be violated — by any agent, reviewer, or human. They express domain rules that are always blocking.

| | CLAUDE.md | CONSTRAINTS.md |
|---|-----------|---------------|
| Content | Process, preferences, tools | Domain invariants |
| Example | "Always push after commit" | "Depth is always local MD" |
| Audience | Claude Code | Everyone — humans, CC, other tools |
| Enforced by | CC directly | Helm reviewers + session agent |
| Violation consequence | Bad workflow | Wrong code, failing tests |

## File Location

`CONSTRAINTS.md` in the repository root. Visible to everyone, not hidden inside `_helm/`.

Opt-in — the file does not exist by default. Create it when a repo has domain invariants worth enforcing.

## Path Resolution

Helm skills resolve the file via:

```bash
git rev-parse --show-toplevel
```

Then read `$(repo-root)/CONSTRAINTS.md`. This works regardless of which subdirectory VS Code opens.

## Format

Plain markdown. One heading per constraint, prose rules underneath. No frontmatter, no YAML.

```markdown
# Constraints

## Coordinate systems
All depth values in the wellbore module use local measured depth (MD, 0+).
Global true vertical depth (TVD) only exists in export mappers.
Never convert between coordinate systems inside domain logic.

## Currency precision
All monetary values use decimal, never floating point.
Rounding happens once, at the presentation layer.

## Well naming
Well identifiers follow the NPD format: XX/YY-ZZ A.
Never parse well names with regex — use WellIdentifier.Parse().
```

Guidelines for writing constraints:
- **Falsifiable** — a reviewer must be able to say "this line violates constraint X"
- **Name concrete modules, types, or values** — not vague guidance
- **No soft language** — "be careful", "consider", "try to" are not constraints
- **Few and short** — aim for under 15 constraints per repo, each a few lines

If something is not blocking, it is not a constraint — put it in CLAUDE.md instead.

## Injection Points

Constraints are injected at three levels:

1. **Session agent (helm-go setup):** Read `CONSTRAINTS.md` as passive guidance during implementation. Prevents violations from being written in the first place.

2. **Plan reviewer (helm-start):** Evaluate whether the plan *proposes* to violate any constraint. Flag as BLOCKING.

3. **Code reviewer (helm-go):** Evaluate whether the diff *actually* violates any constraint. Flag as BLOCKING.

All three receive the full file content via `<CONSTRAINTS_CONTENT>` placeholder. No filtering by path or scope — all constraints apply everywhere, always.

## Worktree Inheritance

`CONSTRAINTS.md` is a tracked file in the repo root. Worktrees created with `git worktree add` inherit it automatically via git. No extra mechanism needed.

## Scope

Always global. All constraints apply to the entire repository. There is no per-directory scoping — constraints should be few enough that injecting all of them everywhere is negligible in token cost.
