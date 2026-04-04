# Task: git /git-pr skill

## Patterns established
- Skill files that use `gh` CLI follow a consistent pattern: try `gh` first, fall back to browser URL with platform detection (Windows `start`, macOS `open`, Linux `xdg-open`)
- When `gh` is determined unavailable early in a skill, later steps should skip `gh` calls and go straight to fallback logic
- `_git/config.yaml` is the future home for git-plugin config (forward-looking, Knatte18/millhouse#13)

## Existing patterns discovered
- Skills auto-discover from `skills/` directory structure — plugin.json has no `skills` array
- Repo detection (`gh repo view` + `git remote get-url` fallback) is duplicated across skills by design — skills are self-contained instruction documents

## Gotchas
- `gh pr view` without arguments checks the current branch's PR — but a transient network failure could be misinterpreted as "no PR exists"
- When skipping steps in a multi-step skill (e.g. skipping fetch+merge after completing an in-progress merge), ensure downstream steps that depend on remote refs still work
