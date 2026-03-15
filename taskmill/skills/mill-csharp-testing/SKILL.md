---
name: mill-csharp-testing
description: Testing conventions for C#/.NET projects. Use when writing tests.
---

# Testing Skill

Swappable testing conventions for C#/.NET projects. Replace or extend this file to match your test framework.

---

## General Principles

See `@taskmill:mill-testing` for language-agnostic rules (assertion strictness, mock discipline, naming).

---

## Framework Configuration

> Replace this section with your chosen framework's conventions.

### Placeholder (xUnit example)

```csharp
// Test class naming: {ClassUnderTest}Tests
public class CsvExporterTests
{
    [Fact]
    public void ExportsAllColumnsForGivenDataSet()
    {
        // Arrange
        var exporter = new CsvExporter(delimiter: ",");

        // Act
        var result = exporter.Export(SampleData.CreateRows(count: 3));

        // Assert
        Assert.Equal(expected: 4, actual: result.Lines.Count); // header + 3 rows
    }
}
```

### Conventions to specify per project

- Test framework: xUnit / NUnit / MSTest
- Assertion library: built-in / FluentAssertions / Shouldly
- Mocking library: Moq / NSubstitute / FakeItEasy (if needed)
- Test project naming convention
- Integration test setup (if applicable)

<!-- Project-specific testing configuration goes here -->
