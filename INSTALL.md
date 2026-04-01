# Install

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed and on your PATH.
- This repository cloned locally (e.g. `c:\Code\millhouse`).

## Global install (copy-paste into terminal)

```
claude plugin marketplace add c:/Code/millhouse
claude plugin install taskmill@millhouse
claude plugin install codeguide@millhouse
claude plugin install conduct@millhouse
claude plugin install code@millhouse
claude plugin install git@millhouse
claude plugin install python@millhouse
claude plugin install csharp@millhouse
```

Taskmill requires Python dependencies (will be removed when Helm replaces taskmill):
```
pip install -r c:/Code/millhouse/plugins/taskmill/requirements.txt
```

## Per-repo setup

Run these inside the target repo after global install:

- **codeguide:** `/codeguide-setup .py .cs` (adjust extensions for your project)
- **helm:** `/helm-setup` (when available)

## Updating

After editing skills or scripts in `plugins/`, re-run the install commands above. Or use `/taskmill-deploy` from within Claude Code.

Close and reopen Claude Code after updating so it picks up changes.
