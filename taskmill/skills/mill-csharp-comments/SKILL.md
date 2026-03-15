---
name: mill-csharp-comments
description: XML doc and inline comment rules for C#/.NET. Use when writing C# comments.
---

# Comments and Documentation Skill

Guidelines for code comments and XML documentation in C#/.NET.

---

## XML documentation

- All `public` methods and classes **must** have `/// <summary>` XML doc comments.
- The doc comment should explain **what** the method does and **why** it exists.
- A reader should understand the method's purpose from its signature + doc comment alone, without reading the implementation.

## Inline comments

- Use inline comments only to explain **why**, never **what**.
- If the code needs a "what" comment, the code itself is unclear — refactor instead.

## Prohibited patterns

- **Never** comment out code. Delete it. Version control handles history.
- **No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").
- **No end-of-line comments.** Place comments on their own line above the code.
