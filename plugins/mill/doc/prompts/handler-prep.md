# Handler Prep — Pre-Verification Reading Pass

N reviewer reports on the source files below will arrive shortly from parallel workers. Before they land, **read the files now and build context** so that when the reports arrive you can verify their citations quickly and accurately.

## Source files to pre-read

<SUBJECT>

## Your task

1. Read each file above using the Read tool.
2. Build working context: purpose, key functions, invariants, cross-file references.
3. Note which files referenced from the bundle might NOT be in the bundle (so you know what extra Read calls you may need when verifying worker claims later).
4. Save your prep notes to this exact path using the Write tool:

```
<NOTES_PATH>
```

The notes should include:

- A brief summary of each file's purpose and scope.
- Key structural decisions, invariants, or conventions you observed.
- Cross-references: what does file A call in file B? Where are backend implementations (not in the bundle) that future worker claims may refer to?
- Questions or ambiguities likely to surface as findings.

Keep the notes compact — this is a reference for yourself, not a consumer-facing review.

5. After writing the notes file, output **ONLY** this single line in stdout:

```
PREP_DONE
```

No other text. The orchestrator treats `PREP_DONE` as a completion signal and reads the notes from the file you wrote.
