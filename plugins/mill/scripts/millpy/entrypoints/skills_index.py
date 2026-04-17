"""
entrypoints/skills_index.py — Scan plugins/*/skills/**/SKILL.md and regenerate
SKILLS.md (repo root) + per-plugin INDEX.md from the frontmatter.

Manual invocation:
    PYTHONPATH=plugins/mill/scripts python -m millpy.entrypoints.skills_index

Deterministic: sorted alphabetically by `name`, written with explicit
``newline="\n"`` to avoid Windows CRLF translation, trailing newline.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import sys
from pathlib import Path


PLUGIN_HEADER = {
    "mill": "# Mill Skills",
    "python": "# Python Skills",
    "csharp": "# C# Skills",
    "weblens": "# Weblens Skills",
    "taskmill-legacy": "# Taskmill-legacy Skills",
}


def scan_skills(repo_root: Path) -> dict[str, list[dict]]:
    """Scan ``repo_root/plugins/*/skills/**/SKILL.md`` and return per-plugin entries.

    For each SKILL.md with a parseable YAML frontmatter containing ``name:`` and
    ``description:``, emit a dict ``{name, description, path, plugin}`` where
    ``path`` is a POSIX-style path relative to ``repo_root``.

    SKILL.md files with missing or malformed frontmatter are logged to stderr
    and skipped — they do not raise.

    Returns a dict keyed by plugin name (first path segment under ``plugins/``),
    value is a list of entries sorted alphabetically by ``name``.
    """
    from millpy.core.config import _parse_yaml_mapping
    from millpy.core.log_util import log

    skills_by_plugin: dict[str, list[dict]] = {}

    plugins_dir = repo_root / "plugins"
    if not plugins_dir.exists():
        return skills_by_plugin

    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        plugin_name = plugin_dir.name
        skills_by_plugin.setdefault(plugin_name, [])

        skill_root = plugin_dir / "skills"
        if not skill_root.exists():
            continue

        for skill_file in sorted(skill_root.rglob("SKILL.md")):
            try:
                text = skill_file.read_text(encoding="utf-8")
            except OSError as exc:
                log("skills_index", f"warning: cannot read {skill_file}: {exc}")
                continue

            fm = _extract_frontmatter(text)
            if fm is None:
                log("skills_index", f"warning: no frontmatter in {skill_file}")
                continue

            try:
                meta = _parse_yaml_mapping(fm)
            except Exception as exc:
                log("skills_index", f"warning: malformed frontmatter in {skill_file}: {exc}")
                continue

            name = meta.get("name")
            description = meta.get("description")
            if not name or not description:
                log(
                    "skills_index",
                    f"warning: missing name/description in {skill_file}",
                )
                continue

            rel = skill_file.relative_to(repo_root).as_posix()
            skills_by_plugin[plugin_name].append(
                {
                    "name": str(name),
                    "description": str(description),
                    "path": rel,
                    "plugin": plugin_name,
                }
            )

        skills_by_plugin[plugin_name].sort(key=lambda e: e["name"])

    return skills_by_plugin


def _extract_frontmatter(text: str) -> str | None:
    """Return the YAML frontmatter block from ``text``, or None if absent.

    A frontmatter block starts with ``---`` on the first line and ends at the
    next ``---`` line. Returns the inner text (no delimiters).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def render_table(entries: list[dict], header: str, base_path: Path) -> str:
    """Render a list of entries as a markdown table.

    ``base_path`` is the directory containing the output file; each entry's
    ``path`` (repo-relative POSIX) is rewritten to be relative to ``base_path``
    so the generated links resolve correctly from the output file's location.
    ``header`` is emitted as the file's h1.
    """
    parts: list[str] = [header, "", "| Skill | Description |", "|---|---|"]
    for entry in sorted(entries, key=lambda e: e["name"]):
        link = _relpath_posix(Path(entry["path"]), base_path)
        desc = entry["description"].replace("\n", " ").strip()
        parts.append(f"| [{entry['name']}]({link}) | {desc} |")
    return "\n".join(parts) + "\n"


def _relpath_posix(target_repo_relative: Path, base_path: Path) -> str:
    """Compute ``target`` relative to ``base_path`` using POSIX separators.

    Both ``target_repo_relative`` and ``base_path`` are treated as repo-relative.
    """
    target_parts = target_repo_relative.parts
    base_parts = base_path.parts
    i = 0
    while i < len(target_parts) and i < len(base_parts) and target_parts[i] == base_parts[i]:
        i += 1
    up = [".."] * (len(base_parts) - i)
    down = list(target_parts[i:])
    if not up and not down:
        return "."
    return "/".join(up + down)


def write_outputs(repo_root: Path, scan_result: dict[str, list[dict]]) -> list[Path]:
    """Write SKILLS.md (combined) and per-plugin INDEX.md files.

    All writes use ``newline="\n"`` so Windows does not translate LF to CRLF —
    keeps the output byte-identical across re-runs and platforms.
    """
    written: list[Path] = []

    combined: list[dict] = []
    for plugin, entries in scan_result.items():
        combined.extend(entries)

    combined_path = repo_root / "SKILLS.md"
    combined_text = render_table(combined, "# Skills", Path("."))
    combined_path.write_text(combined_text, encoding="utf-8", newline="\n")
    written.append(combined_path)

    for plugin, entries in scan_result.items():
        skills_dir = repo_root / "plugins" / plugin / "skills"
        if not skills_dir.exists():
            continue
        index_path = skills_dir / "INDEX.md"
        header = PLUGIN_HEADER.get(plugin, f"# {plugin.capitalize()} Skills")
        base = Path("plugins") / plugin / "skills"
        text = render_table(entries, header, base)
        index_path.write_text(text, encoding="utf-8", newline="\n")
        written.append(index_path)

    return written


def main(argv: list[str] | None = None) -> int:
    """Scan and regenerate SKILLS.md + per-plugin INDEX.md."""
    from millpy.core.paths import repo_root

    try:
        root = repo_root()
    except Exception as exc:
        print(f"[skills_index] Not in a git repository: {exc}", file=sys.stderr)
        return 1

    scan = scan_skills(root)
    written = write_outputs(root, scan)

    total = sum(len(v) for v in scan.values())
    print(f"[skills_index] Scanned {total} skill(s) across {len(scan)} plugin(s).")
    for path in written:
        print(str(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
