# Validation Rules

Post-write validation for `Home.md` (wiki task list), `.millhouse/wiki/active/<slug>/status.md`, and `.millhouse/config.local.yaml`. Skills that write to these files must validate after writing. Rules are structural only — they catch broken file format, not invalid metadata values.

## Home.md (wiki task list)

### File validation

1. **File must exist.** `Home.md` must exist in the wiki clone at `.millhouse/wiki/Home.md`. Created by `mill-setup`. If missing, run `mill-setup`.

### Structural validation

After writing Home.md, verify all of the following:

1. **Single project heading.** Exactly one `# ` heading, at line 1 (e.g., `# Tasks`).
2. **Tasks use `## ` headings.** All task entries are `## ` headings (not `###` or deeper).
3. **Valid phase markers.** If a `## ` heading contains a `[phase]` marker, the phase must be one of: `s`, `active`, `completed`, `done`. Format: `## [phase] Title`. Note: the regex keeps the `[>\w]+` character class so any historical `[>]` markers in old git history still parse; `s` is `\w`-compatible so no regex change was needed for the new marker.
4. **No orphaned content.** No non-blank lines before the first `## ` heading (except the `# ` project heading).

## status.md (`.millhouse/wiki/active/<slug>/status.md`)

### Field validation

After writing status.md, verify fields within the YAML code block (` ```yaml ``` ` fence). Note: status.md lives in the wiki at `.millhouse/wiki/active/<slug>/status.md` and is written exclusively via `millpy.tasks.status_md.append_phase`.

1. **`phase:` is valid.** Must be one of: `discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `pr-pending`, `complete`. Empty/missing `phase:` is allowed only if no task is active.
2. **`task:` is non-empty when phase is set.** If `phase:` has a value, `task:` must also have a non-empty value.

> **Note:** The `phase:` vocabulary in `status.md` is a separate validation domain from `Home.md` phase markers. The `status.md` vocabulary retains the full phase lifecycle (`discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `pr-pending`, `complete`) — `done` is not a valid `phase:` value in `status.md`, only in `Home.md`. Only the `Home.md` marker set is trimmed to `['s', 'active', 'completed', 'done']` (no `[abandoned]`).

## Plan validation (`.millhouse/wiki/active/<slug>/plan/` or `.millhouse/wiki/active/<slug>/plan.md`)

> **Validation exists in code, not prose.** The authoritative check list lives in
> `plugins/mill/scripts/millpy/core/plan_validator.py`. Do not add prose rules
> here that will drift out of sync with the Python module. This section is a
> human-readable summary only.

`plan_validator.validate(loc)` accepts a `PlanLocation` (from `plan_io.resolve_plan_path`)
and returns a list of `ValidationError` objects. All errors have `severity: "BLOCKING"`.
Called at plan-write time by mill-go Phase: Plan, and at pre-dispatch time by
`spawn_reviewer.py` before spawning a plan reviewer.

### Checks that apply to both v1 and v2

| Check | What it verifies |
|---|---|
| Frontmatter keys present | v1 requires: `verify`, `dev-server`, `approved`, `started`. v2 overview requires: `kind: plan-overview`, `task`, `verify`, `dev-server`, `approved`, `started`, `batches`. v2 batch files require: `kind: plan-batch`, `batch-name`, `batch-depends`, `approved`. |
| Required sections | v1: `## Context`, `## Files`, `## Steps`. v2 overview: `## Context`, `## Shared Constraints`, `## Shared Decisions`, `## Batch Graph`, `## All Files Touched`. v2 batch: `## Batch-Specific Context`, `## Batch Files`, `## Steps` (heading required even if body empty). |
| Step card non-empty creates/modifies | Every card must have at least one of `Creates:` or `Modifies:` non-empty. A card with both `none` does nothing and is a structural violation. |
| `depends-on:` references resolve | Integer values in `depends-on:` must reference existing step numbers that precede the current card (within the batch or in batches listed in `batch-depends:`). |

### Checks that apply to v2 only

| Check | What it verifies |
|---|---|
| `Reads:` non-empty | Every v2 step card must have `Reads:` non-empty. v1 cards have no `Reads:` field — this check **must not fire on v1**. |
| `Explore:` ⊆ `Reads:` | Every path in `Explore:` must appear in the card's `Reads:` list. v1-only absence of `Reads:` makes this v2-only. |
| Card numbering globally unique | No duplicate step numbers and no gaps across all batches in the plan directory. |
| `batch-depends:` references resolve | Every batch slug in `batch-depends:` must exist in the overview's `batches:` list. |

### File validation (v2 directory)

`mill-go` Phase: Setup expects the plan to exist at the location stored in `status.md`'s `plan:` field. If missing, mill-go stops and asks the user to re-run Phase: Plan. Existence checking is at the `plan_io.resolve_plan_path` level — it returns `None` when neither v1 nor v2 is present.

### Atomic step granularity (heuristic only)

A step that bundles unrelated file operations is a structural violation. Heuristic: more than ~5 distinct paths in **Modifies:** spanning unrelated subdirectories. This heuristic is guidance — plan reviewers enforce it during plan review (`plan-review.md` evaluation criteria), not programmatically.

See `plugins/mill/doc/formats/plan.md` for the full v2 schema and atomicity invariant.

## .millhouse/config.yaml

After writing, verify all of the following:

1. **Valid YAML.** The file parses without errors.
2. **Required top-level keys.** These keys must be present: `models`, `notifications`.
3. **GitHub section (deprecated).** If a `github:` key exists, it is ignored. No validation required.

Sub-keys under `notifications` are not validated. **Sub-keys under `models` are validated per the rules below.**

### `models:` block validation

`mill-start` and `mill-go` validate the `models:` block on entry. The required slots are:

| Slot | Type | Note |
|---|---|---|
| `models.session` | scalar (string) | Thread A model — mill-start + mill-go Phase 2 |
| `models.implementer` | scalar (string) | Thread B model — Phase 3+4 implementer-orchestrator |
| `models.explore` | scalar (string) | Explore subagent helper |
| `models.discussion-review` | object with required `default` (string) sub-key | Discussion-reviewer (mill-start) |
| `models.plan-review` | object with required `default` (string) sub-key | Plan-reviewer (mill-go Phase 2) |
| `models.code-review` | object with required `default` (string) sub-key | Code-reviewer (Thread B Phase: Review) |

Optional integer-keyed sub-keys are allowed under each per-round object (`discussion-review`, `plan-review`, `code-review`):

| Slot | Type | Note |
|---|---|---|
| `models.discussion-review.1`, `.2`, `.3`, ... | scalar (string) | Per-round overrides; resolution falls back to `default` if absent |
| `models.plan-review.1`, `.2`, `.3`, ... | scalar (string) | Same |
| `models.code-review.1`, `.2`, `.3`, ... | scalar (string) | Same |

The integer keys are compared as strings during lookup. See `overview.md#config-resolution` for the resolution rule.

#### Failure modes

- **Missing required slot:** stop with error `Config schema out of date. Expected models.<slot> (<type>). Run 'mill-setup' to auto-migrate.`
- **Scalar where object expected** (e.g. `plan-review: sonnet` instead of `plan-review: {default: sonnet}`): stop with the same error, explicitly naming the offending slot.
- **Unknown model name in a slot:** NOT a validation failure. Model-name resolution happens in the orchestrator and `spawn-agent.ps1` at call time; unknown names fail loudly there with "not implemented" when the provider lookup misses. Validation only checks shape, not content.
- **Unknown extra keys under `models:`** (e.g. `models.foo: bar`): NOT a validation failure. Warn and proceed. Users may experiment with new slots.

`mill-setup` auto-migration (Step 4b) attempts to fix missing slots and scalar-where-object cases automatically before validation runs. Validation is the safety net for edge cases the migration cannot handle. See `overview.md#config-migration` for the two-layer migration spec.

### `reviewers:` block validation

The `reviewers:` block is a mapping from reviewer-name (string) to recipe objects. It is optional in legacy configs (see `models:` fallback path), but required once `review-modules:` is present.

Each recipe must have:

| Field | Type | Required | Notes |
|---|---|---|---|
| `worker-model` | string | required | Provider name (e.g. `opus`, `sonnet`, `gemini-3-pro`) |
| `worker-count` | int ≥ 1 | required | Number of parallel workers |
| `dispatch` | `tool-use` \| `bulk` | required | Dispatch mode |
| `prompt-template` | string (repo-relative path) | required when `dispatch == 'bulk'` | Bulk prompt template file |
| `handler-model` | string | required when `dispatch == 'bulk'` and `worker-count >= 2` | Handler model name |
| `max-bundle-chars` | int | optional | Default 200000 when dispatch is bulk; absent for tool-use |
| `fallback` | string (reviewer name) | optional | Fallback recipe name on bot-gate |

#### Forbidden combinations for reviewers

- `dispatch == 'tool-use'` AND `worker-count >= 2` → error:
  ```
  reviewer '<name>': dispatch='tool-use' with worker-count >= 2 is not supported. Use dispatch='bulk' for multi-worker ensembles.
  ```
- `dispatch == 'bulk'` AND `prompt-template` absent → error:
  ```
  reviewer '<name>': dispatch='bulk' requires prompt-template
  ```

### `review-modules:` block validation

The `review-modules:` block has three required sub-keys: `discussion`, `plan`, `code`. Each has:

| Field | Type | Required | Notes |
|---|---|---|---|
| `default` | string (reviewer name) | required | Default reviewer name for all rounds |
| `"1"`, `"2"`, ... | string (reviewer name) | optional | Per-round overrides; integer string keys |

**Cross-check:** every reviewer name referenced in `review-modules.*.*` must exist in the `reviewers:` block. Error format:

```
Config schema out of date. Expected reviewers.<name> (object). Run 'mill-setup' to auto-migrate.
```

#### Forbidden combinations for review-modules

- `review-modules.discussion.*` pointing at a reviewer whose `dispatch == 'bulk'` → error:
  ```
  discussion-review cannot use bulk dispatch — no deterministic file scope
  ```

#### Legacy migration

When `review-modules:` is absent, `mill-start` and `mill-go` fall back to the legacy `models.discussion-review`, `models.plan-review`, `models.code-review` blocks. Once `review-modules:` is present, it takes precedence and the legacy blocks become optional. Run `mill-setup` to auto-migrate a legacy config to the new schema.

The round-resolution rule (see `overview.md#config-resolution`) is unchanged: look up `str(round_num)` first, fall back to `default`.

## Failure behavior

If validation fails: report the specific rule violation to the user and stop. Do not attempt to auto-fix — automatic corrections risk making the problem worse.
