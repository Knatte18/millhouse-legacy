# Backlog

- [ ] **Implement Helm plugin**
  Build the Helm plugin from the design docs in plugins/helm/doc/. See implementation-plan.md for phased build order.

- [ ] **Plugin for bypassing Claude's URL refusal**
  Plugin to tweak Claude into reading web pages that it otherwise refuses to read for unclear reasons.

- [ ] **Helm: lokal kanban med on-demand GitHub sync**
  Kanban-oppdateringer mot GitHub API er trege. Ha en lokal kanban-tilstand som oppdateres umiddelbart, og sync til/fra GitHub kun når brukeren eksplisitt ber om det. Folk kan legge inn items på nett, og de hentes inn ved sync.

- [1] **Helm feedback-mekanisme for eksterne tilbakemeldinger**
  En enkel måte for kollegaer, reviewers, eller CI å gi tilbakemeldinger til CC som ikke er tunge nok for CONSTRAINTS.md. Lettvekts korrigeringer som CC skal huske i fremtidige sessions. Forskjell fra constraints (ufravikelige invarianter), memory (per-bruker), og knowledge (per-worktree). Trenger diskusjon om format, plassering, og hvem som leser dem.
  - plan: .llm/plans/2026-04-03-065656-feedback-skill.md
  - started: 2026-04-03-065847
