# Git Skill

Git workflow rules. No exceptions.

---

## Branch Rules

- **NEVER** operate on `main`. Not checkout, not commit, not push. Stay on the branch the user creates.
- **No rebase.** Merging to main happens via Pull Request, manually by the user.
- If on the wrong branch, stop and ask the user.

---

## Commit Rules

### Message format

Title line describing what was done, followed by bullet points for key decisions and design choices:

```
Add CSV export to reports

- Used CsvHelper for streaming serialization
- Added IReportExporter interface for extensibility
- Reused existing column mapping from PDF exporter
```

- Title should summarize the task (often matches the backlog item name).
- Bullet points explain important **decisions**, not every file changed.
- Omit bullet points if the change is trivial and self-explanatory.

### Staging

- Stage files **individually** by name: `git add file1.cs file2.cs`
- **Never** use `git add .` or `git add -A`.
- Review what is being staged before committing.

### Pre-commit hooks

- **Never** use `--no-verify`. Respect pre-commit hooks.
- If a hook fails: fix the issue, re-stage, and commit again.

### No fixup commits

- Do not use `git commit --fixup`. Each commit should be self-contained.

---

## Push

- Push to remote after committing. Set upstream if needed: `git push --set-upstream origin <branch>`.
- **Never** force-push.

