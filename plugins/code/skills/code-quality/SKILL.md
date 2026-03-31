---
name: code-quality
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

- Use full, descriptive names. No abbreviations or acronyms (except established domain abbreviations defined in a docstring).
- The name should convey intent without needing a comment.
- Prefer clarity over brevity: `calculate_pressure_drop` over `calc_p_drop`, `CalculatePressureDrop` over `CalcPDrop`.
- **Encode the domain operation and data source in the name**, not generic verbs. A reader should know what data is produced and from what inputs without reading the implementation.
  - Bad: `process_data`, `build_index`, `get_results`, `transform`, `run`
  - Good: `create_CBI_from_SSB_and_RSI`, `create_postcode_partition_map`, `load_transactions_from_parquet`
- If you cannot name a function precisely, the function is doing too many things — split it.

## File management

- **Prefer editing existing files** over creating new ones.
- Only create new files when structurally necessary.
- Before creating a markdown or documentation file, confirm with the user.
