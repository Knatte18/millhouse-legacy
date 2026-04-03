# Backlog

- [ ] **Helm notifications**
  aktiver og test toast-varsler: Toast er enabled i _helm/config.yaml men aldri testet. Test BurntToast på Windows. Verifiser at helm-go og helm-merge faktisk trigger notifications korrekt.

- [ ] **git /issue skill — opprett issue på dette repoet**
  En /issue skill i git-pluginen som oppretter GitHub issue på repoet du jobber i. Bruker gh issue create. Fallback til browser. Forskjell fra /feedback som alltid går til millhouse.

- [p] **helm-add metadata lines rendered as separate tasks in kanban board**
  Via helm-add i py-repoet ble metadata-linjer (- created, - phase) tolket som separate tasks av kanban.md-extensionen. Trenger fix i format eller helm-add. Fra feedback issue #7.
  - started: 2026-04-03-085401
  - plan: .llm/plans/2026-04-03-090729-fix-kanban-metadata.md
