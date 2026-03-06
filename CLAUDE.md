## Build rules

- **NEVER edit files under `build/` directly.**
    - All source of truth lives in `doc/`.
    - To regenerate build files: run `/mill-build`.
    - To deploy (reinstall plugin): run `/mill-deploy`.
