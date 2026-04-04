# Task: Include design decisions in reviewer prompts

## Patterns established
- Plan `## Context` section uses structured format: summary paragraph + `### Decision: <title>` subsections with `**Why:**` and `**Alternatives rejected:**`
- Both plan-reviewer and code-reviewer prompts have explicit criteria to check against `### Decision:` subsections
- Plan-reviewer criterion: "Design decision alignment" (between Alignment and Completeness)
- Code-reviewer criterion: "Design intent" (between Plan alignment and Correctness)

## Existing patterns discovered
- The plan template exists in two places: `plugins/helm/doc/modules/plans.md` (reference doc) and inline in `plugins/helm/skills/helm-start/SKILL.md` (what actually drives plan generation). Both must be kept in sync.
