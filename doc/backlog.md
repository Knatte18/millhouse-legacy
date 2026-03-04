- [p] **Plan steps should not use slash command syntax**
  Plan steps like 'Run /hanf-skill-build' confuse the LLM executor — it may interpret slash commands as requiring user invocation rather than executing the underlying action itself. Steps should describe concrete actions (e.g. 'Regenerate scripts from updated spec' or 'Run python build_skills.py') instead of referencing slash commands. Update skill-formats.md plan format spec and hanf-finalize-plan command to enforce this
  - plan: .llm/plans/2026-03-04-1423-no-slash-commands-in-plans.md

- [ ] **Incremental skill build**
  Investigate making the build command smart so it only rebuilds files that changed since the last build

