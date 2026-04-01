---
name: helm-receiving-review
description: Decision tree for evaluating reviewer findings. MUST be invoked BEFORE reading any reviewer output.
---

# Receiving-Review Protocol

**MANDATORY:** This skill must be loaded BEFORE you read any reviewer findings — during both plan review and code review. If you have already read the findings, this skill is useless; you have already formed rationalizations.

---

## Core Rule

Default: **fix everything.** The only valid escape is proven harm.

Fixing a finding costs seconds. Leaving it costs compounding debt — every unfixed finding is a pattern the next task copies.

---

## Decision Tree

For each finding:

```
VERIFY: Is the finding factually accurate?
  → NO → PUSH BACK with evidence (cite actual code)
  → YES or UNCERTAIN → continue

HARM CHECK: Would the fix cause demonstrable harm?
  a. Break existing functionality? → PUSH BACK (cite what breaks)
  b. Conflict with a documented design decision? → PUSH BACK (cite the doc)
  c. Destabilize code outside this task's scope? → PUSH BACK (cite the risk)
  → None of the above → FIX IT
```

---

## Forbidden Dismissals

These rationalizations are **never** valid reasons to skip a fix:

- "Low risk" / "low impact"
- "Technically works" / "not build-breaking"
- "Out of scope for this task"
- "Pre-existing issue"
- "Won't change during this project"
- "Cosmetic / style preference"
- "Future task will handle this"

---

## Legitimate Pushback

Pushback is valid **only** when:

1. **Factually wrong** — cite the actual code that disproves the finding
2. **Fix breaks something** — identify what breaks
3. **Conflicts with design doc** — cite the document and passage
4. **Destabilizes other work** — cite what is affected and why

---

## Applying This Protocol

After loading this skill, process each reviewer finding through the decision tree above. For each finding, state:

1. The finding
2. Your VERIFY assessment (accurate / inaccurate / uncertain)
3. Your HARM CHECK result (which harm category, if any)
4. Your action: FIX or PUSH BACK (with cited evidence)
