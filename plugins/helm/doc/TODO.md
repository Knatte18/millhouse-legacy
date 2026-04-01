# Helm — TODO

Ting som må gjøres utenom selve Helm-designet.

## Done

- [x] **Opprett `conduct`-plugin.** Conversation + workflow skills. Erstatter orchestration.
- [x] **Fjern `orchestration`-plugin.** Erstattet av conduct.
- [x] **Oppdater `~/.claude/CLAUDE.md`** til å laste `conduct:conversation` + `conduct:workflow`.
- [x] **Oppdater `code:testing`** med coverage-krav, TDD discipline, no shallow tests.

## Helm — implementeringsklare items fra design docs

- [ ] **Definer format-validering for tracked files.** Spesielt `_helm/config.yaml`. Hook eller lightweight script. Se open-questions.md.
- [ ] **Legg til `.scratch/` i `.gitignore`-mal.** Generell scratch-mappe for CC-operasjoner utenfor plugins.

## Testing

- [ ] **Verifiser `code:testing`-oppdateringen** fungerer i praksis. Test med et reelt prosjekt.

## Taskmill-utfasing

- [ ] **Fjern taskmill-plugin** når Helm er operativ.
