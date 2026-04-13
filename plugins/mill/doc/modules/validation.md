# Validation Rules

Post-write validation for `tasks.md`, `_millhouse/task/status.md`, and `_millhouse/config.yaml`. Skills that write to these files must validate after writing. Rules are structural only — they catch broken file format, not invalid metadata values.

## tasks.md (project root)

### File validation

1. **File must exist.** `tasks.md` must exist in the project root (the working directory where `_millhouse/` lives). Created by `mill-setup`. If missing, run `mill-setup`.

### Structural validation

After writing tasks.md, verify all of the following:

1. **Single project heading.** Exactly one `# ` heading, at line 1 (e.g., `# Tasks`).
2. **Tasks use `## ` headings.** All task entries are `## ` headings (not `###` or deeper).
3. **Valid phase markers.** If a `## ` heading contains a `[phase]` marker, the phase must be one of: `>`, `active`, `done`, `abandoned`. Format: `## [phase] Title`. Note: the regex `\[(\w+)\]` does not match `[>]` — use `\[([>\w]+)\]` when validating programmatically.
4. **No orphaned content.** No non-blank lines before the first `## ` heading (except the `# ` project heading).

## status.md (`_millhouse/task/status.md`)

### Field validation

After writing status.md, verify fields within the YAML code block (` ```yaml ``` ` fence):

1. **`phase:` is valid.** Must be one of: `discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `pr-pending`, `complete`. Empty/missing `phase:` is allowed only if no task is active.
2. **`task:` is non-empty when phase is set.** If `phase:` has a value, `task:` must also have a non-empty value.

> **Note:** The `phase:` vocabulary in `status.md` is a separate validation domain from `tasks.md` phase markers. The `status.md` vocabulary retains the full phase lifecycle (`discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `pr-pending`, `complete`) — `done` is not a valid `phase:` value in `status.md`, only in `tasks.md`. Only the `tasks.md` marker set is trimmed to `['>', 'active', 'done', 'abandoned']`.

## plan.md (`_millhouse/task/plan.md`)

### File validation

1. **File exists when expected.** `mill-go` Phase: Setup requires `_millhouse/task/plan.md` to exist (it was written by Phase: Plan and approved by Phase: Plan Review). If missing on Setup entry, mill-go stops with an error pointing the user to re-run mill-go.

### Structural validation

After writing plan.md (Phase: Plan), verify all of the following:

1. **Frontmatter present.** YAML frontmatter must include keys `verify`, `dev-server`, `approved`, `started`. The `approved` value is `true` or `false`. The `started` value matches `YYYYMMDD-HHMMSS` (UTC).
2. **Required sections.** A single `# <Task Title>` h1, and h2 sections `## Context`, `## Files`, `## Steps` (in that order). Other h2 sections may follow.
3. **Step structure.** Each `### Step N: <description>` heading must be followed by a step card containing the bolded fields **Creates:**, **Modifies:**, **Requirements:**, **Explore:**, **Test approach:**, **Key test scenarios:**, **Commit:**. The **TDD:** field is optional.
4. **Atomic step granularity.** A step that bundles unrelated file operations is a structural violation. Heuristic: more than ~5 distinct paths in **Modifies:** that span unrelated subdirectories. The heuristic is documented as guidance — reviewers enforce it during plan review (`plan-review.md` evaluation criteria), not programmatically.
5. **Decision subsections.** Each `### Decision: <title>` inside `## Context` must contain `**Why:**` and `**Alternatives rejected:**` lines.

See `doc/modules/plan-format.md` for the full schema and the atomicity invariant.

## _millhouse/config.yaml

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
