# Knowledge Curation — Removed

This module was inspired by Autoboard's inter-layer knowledge curation, but Helm's sequential model makes it redundant:

- **Autoboard** runs parallel sessions that can't see each other's code — knowledge curation is the only way to pass context between layers.
- **Helm** is sequential — each task sees prior commits directly. The code *is* the knowledge.

## Where context lives instead

| What | Where |
|------|-------|
| Design decisions from discussion | `## Context` + `### Decision:` subsections in the plan |
| Architectural conventions | Code structure, codeguide, `CONSTRAINTS.md` |
| Project-wide rules | `CLAUDE.md` |
| History of changes | Git log |

The `_helm/knowledge/` directory is no longer created or used.
