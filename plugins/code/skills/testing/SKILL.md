---
name: testing
description: Language-agnostic testing principles. Use when writing or reviewing tests.
---

# Testing Skill

Universal testing principles. Language-specific skills build on these.

---

## Assertions

- **Strict equality.** Prefer exact equality over loose containment checks.
  - Bad: `assert "valid" in result`
  - Good: `assert result == "valid"`
- Never assert truthiness alone (`assert result`) — assert the expected value.

## Mocking

- **Last resort.** Prefer fakes, stubs, or in-memory implementations over mocking frameworks.
- **Never mock your own code.** Mock only external dependencies you do not control.
- **Prefer record/replay** for network traffic over hand-written mocks.
- **Terminology matters:**
  - *Mock* — replaces behavior using a mocking framework.
  - *Fake* — a lightweight working implementation (e.g. in-memory database).
  - *Stub* — returns fixed data without real logic.
  - Use the correct term. Do not call everything a "mock".

## Naming

- Test names describe **behavior**, not implementation. The name should read as a sentence describing what is expected.
- Do not include the word "test" in the name beyond the required framework prefix (e.g. `test_` in Python, `Test` prefix in Go).
