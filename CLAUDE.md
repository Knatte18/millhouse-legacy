## Build rules

- **NEVER edit files under `build/` or `~/.claude/` directly.** 
    - All source of truth lives in `doc/`.
    - To regenerate build files: run `/mill-build`.
    - To deploy: run `/mill-deploy`.
