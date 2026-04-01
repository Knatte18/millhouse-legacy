---
name: testing
description: Language-agnostic testing principles. Use when writing or reviewing tests.
---

# Testing Skill

Universal testing principles. Language-specific skills build on these.

---

## Coverage

- **Test behavior, not implementation.** Tests should verify observable outcomes, not internal state or implementation details. If you refactor the internals, the tests should still pass.
- **Every test path.** Happy path is the minimum. Always cover:
  - **Error paths** — invalid input, missing data, unauthorized access, network failure
  - **Edge cases** — empty collections, null/undefined, boundary values, concurrent access
  - **Negative cases** — what should NOT happen (no side effects, no data leak)
- **All existing tests must pass.** Never break existing tests. Run the full suite, not just new/related tests.
- **No shallow tests.** A test that asserts "function returned something" is worthless. Assert the specific value, shape, and side effects.
  - Bad: `assert result is not None`
  - Good: `assert result.status == "active" and result.created_at > start_time`

## TDD Discipline

When TDD is specified:

1. **RED:** Write the test first. Run it. It MUST fail. If it passes, the test is wrong — it's not testing what you think.
2. **GREEN:** Write the minimum implementation to make it pass. No more.
3. **REFACTOR:** Clean up, keeping tests green.

Skipping RED verification (writing implementation before seeing the test fail) produces tests that confirm implementation rather than specify behavior.

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
