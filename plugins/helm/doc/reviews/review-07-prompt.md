# Review 07 — Final verification

**Date:** 2026-04-03
**Scope:** All SKILL.md files, all doc/modules/, config.yaml, .kanban.md
**Branch:** helm-phase1
**Context:** Review-06 found 1 BLOCKING, 4 CONCERN, 4 NIT. All fixed. This is the final verification pass.

---

## Instructions

Du er en uavhengig reviewer. Ingen kontekst fra tidligere samtaler.

Les i denne rekkefølgen:
1. `plugins/helm/doc/reviews/review-06-result.md` — forrige review
2. Alle SKILL.md-filer i `plugins/helm/skills/*/SKILL.md`
3. `plugins/helm/doc/overview.md`
4. `plugins/helm/doc/decisions.md`
5. `plugins/helm/doc/modules/*.md`

## Fokus

1. **Verifiser review-06 fixes:** For hvert funn (B7, C9-C12, N7-N10): FIXED eller STILL OPEN.
2. **Steg-nummerering i helm-go:** C9 var en regresjon fra forrige fix. Verifiser at nummereringen nå er konsistent gjennom hele filen — ingen duplikater, ingen hull.
3. **Commit/push etter alle kanban-endringer:** Verifiser at ALLE steder som endrer `.kanban.md` har commit+push etterpå (helm-start, helm-go, helm-merge, helm-abandon).
4. **Stale referanser:** Søk etter referanser til fjernede filer (merge.md, skills.md, notifications.md, failures.md, kanban.md, reviews.md, TODO.md, backlog.md, open-questions.md).
5. **Intern konsistens:** Motstridende instruksjoner mellom skills, docs, eller config.

## Output

Skriv resultatet til `plugins/helm/doc/reviews/review-07-result.md`.

Hvis ingen BLOCKING eller CONCERN funn: skriv "APPROVED — Helm is ready for end-to-end testing."

Ikke gjør endringer — kun rapporter funn.
