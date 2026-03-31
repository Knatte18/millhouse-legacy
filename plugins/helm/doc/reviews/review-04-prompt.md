# Helm Design Review — Round 4 (Final)

**INSTRUCTIONS:** This file is a review prompt. Do NOT review this file itself. Read the files listed below, then write your review to the output path at the bottom. This prompt tells you WHAT to review and HOW — the design documents listed below are what you're reviewing.

You are reviewing the Helm plugin design for **implementability**. The question is: can an implementer build this plugin from these docs alone, without asking clarifying questions?

## Read These Files

### Helm design
1. `C:\Code\millhouse\plugins\helm\doc\overview.md` — read first
2. All files in `C:\Code\millhouse\plugins\helm\doc\modules\` — read all of them
3. `C:\Code\millhouse\plugins\helm\doc\TODO.md` — remaining items

### Previous reviews
4. `C:\Code\millhouse\plugins\helm\doc\reviews\review-02-result.md`
5. `C:\Code\millhouse\plugins\helm\doc\reviews\review-03-result.md`

### Existing plugins (what the implementer has to work with)
6. Conduct plugin: `C:\Code\millhouse\plugins\conduct\` — all files
7. Codeguide plugin: `C:\Code\millhouse\plugins\codeguide\skills\*\SKILL.md` — all skills
8. Code plugin: `C:\Code\millhouse\plugins\code\skills\*\SKILL.md` — especially `testing/SKILL.md`
9. Git plugin: `C:\Code\millhouse\plugins\git\skills\*\SKILL.md`
10. Taskmill plugin: `C:\Code\millhouse\plugins\taskmill\` — skills and scripts (being replaced by Helm)

### Source material
11. Autoboard: `C:\Code\autoboard` — skim `skills/session-workflow/SKILL.md`, `skills/receiving-review/SKILL.md`, `agents/plan-reviewer.md`, `agents/code-reviewer.md` for comparison

### Repo context
12. `C:\Code\millhouse\CLAUDE.md`
13. `C:\Code\millhouse\INSTALL.md`

## Primary Focus: Implementability

For each skill (`helm-start`, `helm-go`, `helm-add`, `helm-merge`, `helm-status`, `helm-abandon`, `helm-commit`), answer:

1. **Can I write this SKILL.md right now?** Is there enough detail to write the actual skill file that CC will load and follow? If not, what's missing?
2. **Are the inputs and outputs clear?** What does the skill read? What does it write? What state does it expect?
3. **Are the error paths defined?** What happens when each step fails? Is there always a next action?
4. **Are there ambiguities?** Places where two reasonable implementers would make different choices?
5. **Are there contradictions?** Does any doc file say something that conflicts with another?

## Secondary Focus: Completeness

- Is the `_helm/config.yaml` format fully defined? Could you write a valid one from the docs?
- Is the handoff brief format fully defined?
- Is the `_helm/scratch/status.md` format fully defined?
- Is the GitHub Projects setup flow complete enough to execute step by step?
- Are the plan reviewer and code reviewer agent prompts detailed enough to produce consistent behavior?
- Is the receiving-review protocol complete enough to be a standalone skill?
- Is the systematic debugging protocol in failures.md actionable?

## Tertiary Focus: What's Missing

- Any scenarios not covered? (worktree from worktree from worktree, concurrent helm-start in two windows, user edits files manually during helm-go, github API rate limiting)
- Any files that should exist in `plugins/helm/` that aren't mentioned? (plugin.json, settings.json, skill directories)
- Is the relationship between Helm and other plugins (conduct, codeguide, code, git) clear enough?

## What Changed Since Round 3

- Resume protocol: commit after each step, check git log on restart
- Test baseline: capture pre-existing failures before work starts
- Continuous progress: status.md updated every step
- Systematic debugging protocol in failures.md
- Decisions register in knowledge/
- Agent model selection (opus/sonnet/haiku per role)
- Coherence audits removed — replaced by strengthened code reviewer with codeguide context
- Dimensions system removed — existing always-on skills cover quality
- Code reviewer now receives codeguide Overview, greps for utility duplication

## Output Format

### Blocking Issues
Issues that would stop an implementer cold. For each:
- **What:** one sentence
- **Where:** which doc file and section
- **Why:** why an implementer can't proceed
- **Suggestion:** what needs to be added or clarified

### Ambiguities
Places where two implementers would make different choices. For each:
- **What:** the ambiguous point
- **Where:** which doc file
- **Options:** what the two choices are
- **Recommendation:** which to pick and why

### Missing Specs
Things that need to exist but aren't documented. For each:
- **What:** what's missing
- **Why:** why it's needed
- **Suggestion:** what it should contain

### Strengths
What's well-specified and implementation-ready.

### Implementation Order
If you were building this, what order would you implement the skills in? What's the minimum viable subset?

Write your review to `C:\Code\millhouse\plugins\helm\doc\reviews\review-04-result.md`.
