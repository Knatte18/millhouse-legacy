---
name: csharp-build
description: Build and test commands for C#/.NET. Use after completing a task.
---

# Build Skill

Build and test configuration for C#/.NET projects.

---

## Build Commands

Run these commands after completing a task to verify correctness:

```bash
dotnet build
dotnet test
```

## Failure Handling

- If **build fails**: analyze the error, fix the issue, and retry.
- If **tests fail**: analyze the failure, fix the code or test, and retry.
- If a fix requires changes beyond the current task's scope: stop and report the issue to the user.
- Do **not** skip or disable failing tests.

---

## Project Configuration

> Customize per project. Specify which solution/project to build and test.

### Test discovery

Before running tests, verify the project is testable:

1. **Solution file:** Look for `*.sln` files in the project root. If found, `dotnet build` and `dotnet test` operate on the solution (discovers all projects automatically).
2. **Test projects:** If no solution file, look for `*.csproj` files. Test projects follow naming conventions: `*.Tests.csproj`, `*.Test.csproj`, or `*Tests.csproj`. Check for test framework package references (`xunit`, `NUnit`, `MSTest`) to confirm a project is a test project.
3. **No tests:** If no test projects are found, report "No test projects found" rather than running `dotnet test` on a non-test project.

### Defaults

- Build the solution or project in the current working directory.
- Run all tests in the test project associated with the current project.

### Per-project overrides

Specify these when the defaults don't apply:

- Solution file path (if not in current directory)
- Specific test project to run
- Build configuration (Debug/Release)
- Additional build flags

<!-- Project-specific build configuration goes here -->
