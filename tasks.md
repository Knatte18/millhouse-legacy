# Tasks


## Self-reinforcement by automated bug-reporting and no hardcoded templates in skill files

- Self-reinforcement: The two orchestrators (and potentailly also some of the other subthreads): IF a clear bug is detected by the thread, it can ITSELF invoke the "millhouse-issue" skill and report the bug. 
Perhaps wait to do this until the thread's task is fully done. Then an accumulated reports can be destilled to create an accurate bug-issue for the millhous eto be set. 
I can then manually pull down the issues, have Opus analyse them as an ensamble, and fix in one-go.

- Do not hardcode templates in a skill: INGEN av skillene som oppretter filer skal ha hardkodet template. Jeg ser at f.eks step *Step 4c i mill-setup har en hardkodet "config". Vi har laget "millhouse-config.yaml" som en template som skal bruke i stedet. INGEN slik hardkodet template skal inn i noen skill. Det skal brukes en template-fil i stedet. Dette gjør det mye enklere å ender templaten. Sjekk også om det er noen andre skill som gjør dette. 


## Planner-grouped plan review for large plans 
- When a plan has 30+ cards, per-card bulk review + holistic tool-use review may not catch inter-group issues effectively. Add an optional Planner-grouped review mode where Planner creates ad-hoc review groups (overlapping subsets of cards) and spawns one reviewer per group in parallel. Same card can appear in multiple groups. Pure Planner-side change — no plan format changes needed.


## Track task state across machines (W4 — needs design)

Invert the `_millhouse/` gitignore so task state (discussion, plan, status, reviews) travels with the branch. Motivated empirically by the millpy task's Step 33, where a gitignored `config.yaml` silently dropped out of an atomic bundle commit. Do not start implementation until the open design questions in the proposal are answered (gitignore granularity, commit cadence, config split, two-machine race handling, `mill-merge` cleanup contract).

**Design doc:** [plugins/mill/doc/proposals/04-track-task-state.md](plugins/mill/doc/proposals/04-track-task-state.md)

