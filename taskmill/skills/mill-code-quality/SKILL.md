---
name: mill-code-quality
description: Strict, clean code guidelines. Use before editing code.
---

# Code Quality Skill

Guidelines for writing strict, clean code. Language-agnostic.

---

## Strict over forgiving

- **Assert inputs.** Use preconditions, guard clauses, and schema validation. Throw on violations.
- **No union types or loose typing.** Be explicit about what a method accepts and returns.
- **No defensive try/catch.** Let exceptions propagate to where they can be handled meaningfully.
- **No legacy fallbacks.** Remove backwards-compatibility code. If something is unused, delete it.

## Naming

- Use full, descriptive names. No abbreviations or acronyms.
- The name should convey intent without needing a comment.
- Prefer clarity over brevity: `calculate_pressure_drop` over `calc_p_drop`, `CalculatePressureDrop` over `CalcPDrop`.

## File management

- **Prefer editing existing files** over creating new ones.
- Only create new files when structurally necessary.
- Before creating a markdown or documentation file, confirm with the user.
