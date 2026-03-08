# CLAUDE.md
Instructions for Claude Code when working in this repository.

## Background
- This repos is based on a repo by Craig Motlin. When refering to "what Motlin does", I am referring to his code and repo. The repo can be found here: "C:\Code\motlin-claude-code-plugins". 

## Build rules

- **NEVER edit files under `build/` directly.**
    - All source of truth lives in `doc/`.
    - To regenerate build files: run `/mill-build`.
    - To deploy (reinstall plugin): run `/mill-deploy`.
