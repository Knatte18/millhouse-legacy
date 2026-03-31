# codeguide

Navigation-first documentation system for AI-assisted codebases.

Provides routing guides (`_codeguide/`) that direct Claude Code to the right source files before reading them.

Installed globally as part of the millhouse marketplace. Per-repo setup via `/codeguide-setup`.

## Install

See [INSTALL.md](INSTALL.md).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full skill/hook/workflow reference.

## Usage

After install and setup:

1. Edit `_codeguide/config.yaml` — set your source file extensions
2. Run `/codeguide-generate <project>` to create docs for a project
3. Claude Code will now route through `_codeguide/` before searching

### Skills

| Skill | Purpose |
|---|---|
| `/codeguide-setup` | All setup: first-time init, refresh, subfolder activation |
| `/codeguide-generate` | Create docs for undocumented source files (heavy, scoped) |
| `/codeguide-maintain` | Fix existing docs: content, structure, pointers, links (heavy, scoped) |
| `/codeguide-update` | Generate + maintain for recently changed files (light, commit-time) |
| `/review-navigation` | Review violation logs for guide improvement |

### Local rules

`_codeguide/local-rules.md` holds repo-specific documentation rules. These are applied on top of the generic DocumentationGuide.md by the skills.

## File ownership

| File | Owner | On update |
|---|---|---|
| `_codeguide/modules/DocumentationGuide.md` | Plugin | Overwritten by `/codeguide-setup` |
| `_codeguide/NavigationHooks.md` | Plugin | Overwritten by `/codeguide-setup` |
| `_codeguide/cgignore.md` | User | Created from template, never overwritten |
| `_codeguide/config.yaml` | User | New keys merged by `/codeguide-setup` |
| `_codeguide/local-rules.md` | User | Preserved |
| `_codeguide/cgexclude.md` | User | Preserved |
| `_codeguide/Overview.md` | User | Preserved |
| `_codeguide/modules/*.md` | User | Preserved |
| `_codeguide/root.txt` | Generated | Recreated by `/codeguide-setup` |

## Updating

Re-install via `./install-local.sh`, then run `/codeguide-setup` to update plugin-owned files.
