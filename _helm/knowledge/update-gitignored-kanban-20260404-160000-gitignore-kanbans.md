# Task: Update helm skills for gitignored kanban boards

## Patterns established
- All 4 kanban board files are gitignored and local-only — no git staging, no conflict rules
- Autonomous skills (helm-go, helm-merge) auto-create missing board files from template before writing
- Interactive skills (helm-start) stop and tell user to run helm-setup if files are missing
- Template for missing board file: `# <Project>` + blank line + `## <Column>` + newline

## Existing patterns discovered
- helm-spawn.ps1 already creates all 4 kanban files directly in new worktrees — no git tracking needed for handoff
- validation.md "do not auto-fix" policy means auto-creation guards belong in skills, not in validation

## Gotchas
- helm-setup generates CLAUDE.md content into target repos — any kanban rule change must also update the template in helm-setup/SKILL.md
- helm-abandon also references kanban staging — easy to miss since it's not in the typical helm-start → helm-go → helm-merge flow
- Historical review docs (review-05-result.md, review-06-result.md) reference old conflict rules — these are immutable records, not live instructions
