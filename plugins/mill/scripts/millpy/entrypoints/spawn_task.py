"""
entrypoints/spawn_task.py — Task spawner for millpy (live).

Reads tasks.md, picks the next task via the unified picker
(``pick_task``), claims it (changes to [active]), creates the
worktree, writes status.md, and updates the parent's tasks.md.

Picker rules: filter out [active], [done], [abandoned] from the
candidate pool. Fast-path: if any [s] task exists, pick the first one
without prompting. Numbered-fallback: otherwise present a numbered list
of unmarked tasks and prompt the user to choose. Empty mode: no [s] and
no unmarked tasks → print a hint and exit 0.

Prose-paragraph parser fix (Proposal 02 Fix C): tasks_md.parse handles both
bullet-list and prose-paragraph task bodies.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import argparse
import datetime
import re
import shutil
import sys
from pathlib import Path, PurePosixPath


def pick_task(tasks):
    """Pick the next task from a list.

    Returns a tuple ``(mode, picked, candidates)``:

    - ``mode == "fast-path"``: ``picked`` is the first ``[s]`` task in file
      order; ``candidates`` is empty.
    - ``mode == "numbered"``: ``picked`` is ``None``; ``candidates`` is the
      list of unmarked tasks (phase is ``None``), in file order, that the
      caller should present to the user for numeric selection.
    - ``mode == "empty"``: ``picked`` is ``None``; ``candidates`` is empty
      (no pickable tasks exist).

    ``[active]``, ``[done]``, and ``[abandoned]`` phases are filtered out of
    both the fast-path and the numbered candidate pool — they are managed
    elsewhere (mill-start, mill-merge, mill-abandon, mill-cleanup).
    """
    fast = next((t for t in tasks if t.phase == "s"), None)
    if fast is not None:
        return ("fast-path", fast, [])
    candidates = [t for t in tasks if t.phase is None]
    if not candidates:
        return ("empty", None, [])
    return ("numbered", None, candidates)


def main(argv: list[str] | None = None) -> int:
    """Spawn a worktree for the next pickable task in tasks.md.

    Parameters
    ----------
    argv:
        Argument vector. Defaults to sys.argv[1:].

    Returns
    -------
    int
        Exit code (0 = success, non-zero = error).
    """
    from millpy.core.config import ConfigError, load
    from millpy.core.git_ops import current_branch, git
    from millpy.core.log_util import log
    from millpy.core.paths import cwd_offset, project_root, repo_root
    from millpy.core.subprocess_util import run as subprocess_run
    from millpy.tasks import tasks_md

    parser = argparse.ArgumentParser(
        prog="spawn_task",
        description="Spawn a worktree for the next pickable task in tasks.md.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would happen without making changes.",
    )
    parser.add_argument(
        "--vscode",
        action="store_true",
        default=False,
        help="Open the new worktree in VS Code after creation.",
    )

    args = parser.parse_args(argv)

    try:
        root = project_root()
        git_root = repo_root()
    except Exception as exc:
        print(f"[spawn_task] Not in a git repository: {exc}", file=sys.stderr)
        return 1

    # nested_offset = path from git toplevel down to the mill project root.
    # Flat layouts: "." (project == git toplevel).
    # Nested layouts: e.g. "projects/sub" when `_millhouse/` lives below the
    # git toplevel.
    _nested_parts = root.resolve().relative_to(git_root.resolve()).parts
    nested_offset = PurePosixPath(*_nested_parts) if _nested_parts else PurePosixPath(".")

    config_path = root / "_millhouse" / "config.yaml"
    if not config_path.exists():
        print(
            "[spawn_task] mill-setup has not been run. Please run mill-setup first.",
            file=sys.stderr,
        )
        return 1

    tasks_path = root / "tasks.md"
    if not tasks_path.exists():
        print(
            f"[spawn_task] tasks.md not found at {tasks_path}. Run mill-setup first.",
            file=sys.stderr,
        )
        return 1

    # Parse tasks.md — exercises prose-paragraph parser (Fix C)
    tasks = tasks_md.parse(tasks_path)
    mode, spawn_task, candidates = pick_task(tasks)
    if mode == "empty":
        print(
            "[spawn_task] No pickable tasks (all tasks are [active], [done], "
            "or [abandoned], and no [s] task or unmarked task exists). "
            "Run mill-add to add a task.",
            file=sys.stderr,
        )
        return 0
    if mode == "numbered":
        print("Pick a task:")
        for i, t in enumerate(candidates, start=1):
            print(f"  {i}) {t.title}")
        try:
            raw = input("Pick a task number: ")
        except EOFError:
            print("[spawn_task] No input available for numbered picker.", file=sys.stderr)
            return 1
        try:
            choice = int(raw.strip())
        except ValueError:
            print(f"[spawn_task] Not a number: {raw!r}", file=sys.stderr)
            return 1
        if choice < 1 or choice > len(candidates):
            print(
                f"[spawn_task] Choice {choice} out of range (1..{len(candidates)}).",
                file=sys.stderr,
            )
            return 1
        spawn_task = candidates[choice - 1]

    task_title = spawn_task.title
    task_body = spawn_task.body

    # Extract task description from body (prose or bullets)
    task_description = _extract_description(task_body, task_title)

    # Generate slug
    slug = re.sub(r"\s+", "-", task_title.lower())
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    if len(slug) > 20:
        slug = slug[:20]
    slug = slug.rstrip("-")

    # Read branch prefix from config
    branch_prefix = _read_branch_prefix(config_path)
    if branch_prefix:
        branch_name = f"{branch_prefix}/{slug}"
    else:
        branch_name = slug

    log("spawn_task", f"Task: {task_title}")
    log("spawn_task", f"Branch: {branch_name}")

    if args.dry_run:
        print(f"[DryRun] Would write handoff to _millhouse/handoff.md")
        print(f"[DryRun] Would claim (set to [active]) task '{task_title}' in tasks.md.")
        print(f"[DryRun] Would create worktree (branch: {branch_name})")
        print(f"[DryRun] Would copy _millhouse/ (excluding task/, scratch/, children/) to new worktree")
        print(f"[DryRun] Would write status.md in new worktree")
        return 0

    # Claim the picked task (set phase to 'active') in tasks.md
    updated_tasks = tasks_md.render(
        [t if t is not spawn_task else _claim_task(t) for t in tasks]
    )

    # Validate updated tasks.md — write to a temp file for validate()
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp_f:
        tmp_f.write(updated_tasks)
        tmp_path = Path(tmp_f.name)
    try:
        validation_errors = tasks_md.validate(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    if validation_errors:
        for err in validation_errors:
            print(f"[spawn_task] Validation error: {err}", file=sys.stderr)
        return 1

    # Read parent branch
    try:
        parent_branch = current_branch(cwd=root)
    except Exception:
        parent_branch = "unknown"

    # Write handoff to parent _millhouse/handoff.md
    handoff_path = root / "_millhouse" / "handoff.md"
    _write_handoff(handoff_path, task_title, task_description, parent_branch, root, config_path)

    # Write updated tasks.md and commit
    tasks_path.write_text(updated_tasks, encoding="utf-8", newline="\n")

    tasks_rel = str(tasks_path.relative_to(root)).replace("\\", "/")
    try:
        git(["add", tasks_rel], cwd=root)
        git(["commit", "-m", f"task: claim {task_title}"], cwd=root)
        git(["push"], cwd=root)
    except Exception as exc:
        log("spawn_task", f"Git commit/push failed: {exc}")

    # Create worktree via git worktree add. worktrees_dir is the sibling of
    # the git toplevel (not the mill project root) — `git worktree add` only
    # operates at the git-repo level, and nesting the worktrees directory
    # inside the same git repo is not safe.
    worktrees_dir = git_root.parent / f"{git_root.name}.worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    project_path = worktrees_dir / slug

    result = git(
        ["worktree", "add", "-b", branch_name, str(project_path)],
        cwd=git_root,
    )
    if result.returncode != 0:
        print(f"[spawn_task] git worktree add failed: {result.stderr}", file=sys.stderr)
        return 1

    log("spawn_task", f"Worktree created at {project_path}")

    # project_in_worktree — the mill-project-root inside the new worktree.
    # Flat layouts: equals project_path (the git toplevel of the worktree).
    # Nested layouts: project_path / <nested_offset>, e.g.
    # "<git>.worktrees/<slug>/projects/sub".
    if str(nested_offset) == ".":
        project_in_worktree = project_path
    else:
        project_in_worktree = project_path / str(nested_offset)

    # Write .vscode/settings.json with a unique worktree color. Pass the
    # explicit git-level worktrees_dir so sibling-color scanning sees all
    # sibling worktrees regardless of layout.
    _write_vscode_settings(
        project_in_worktree, slug, root, config_path, worktrees_dir=worktrees_dir
    )

    # Copy _millhouse/ (excluding task/, scratch/, children/) to the mill
    # project root inside the worktree (deeper than project_path in nested
    # layouts).
    src_millhouse = root / "_millhouse"
    dst_millhouse = project_in_worktree / "_millhouse"
    dst_millhouse.mkdir(parents=True, exist_ok=True)

    exclude = {"task", "scratch", "children"}
    if src_millhouse.exists():
        for item in src_millhouse.iterdir():
            if item.name in exclude:
                continue
            dst = dst_millhouse / item.name
            if item.is_dir():
                shutil.copytree(str(item), str(dst), dirs_exist_ok=True)
            else:
                shutil.copy2(str(item), str(dst))

    # Create scratch and task structures
    (project_in_worktree / "_millhouse" / "scratch" / "reviews").mkdir(parents=True, exist_ok=True)
    (project_in_worktree / "_millhouse" / "task" / "reviews").mkdir(parents=True, exist_ok=True)

    # Write status.md
    status_path = project_in_worktree / "_millhouse" / "task" / "status.md"
    _write_status(status_path, task_title, task_description, parent_branch)

    # Write child registry entry in parent _millhouse/children/
    children_dir = root / "_millhouse" / "children"
    children_dir.mkdir(parents=True, exist_ok=True)

    ts_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_file = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    child_filename = f"{ts_file}-{slug}.md"
    child_path = children_dir / child_filename

    # Collision handling
    if child_path.exists():
        suffix = 2
        while (children_dir / f"{ts_file}-{slug}-{suffix}.md").exists():
            suffix += 1
        child_filename = f"{ts_file}-{slug}-{suffix}.md"
        child_path = children_dir / child_filename

    child_content = (
        f"---\n"
        f"task: {task_title}\n"
        f"branch: {branch_name}\n"
        f"worktree: {project_path.as_posix()}\n"
        f"status: active\n"
        f"spawned: {ts_iso}\n"
        f"---\n"
        f"\n"
        f"## Summary\n"
        f"{task_description}\n"
    )
    child_path.write_text(child_content, encoding="utf-8", newline="\n")
    log("spawn_task", f"Child registry: {child_filename}")

    # Open VS Code if requested. Apply the cwd-offset rule so VS Code opens
    # the subfolder matching the orchestrator's current cwd. cwd_offset
    # includes both the nested-project offset (project lives below git
    # toplevel) and any further subfolder the user was in.
    if args.vscode:
        code = shutil.which("code.cmd") or shutil.which("code")
        if code:
            try:
                vscode_offset = cwd_offset()
            except Exception as exc:
                log("spawn_task", f"cwd_offset failed, opening project_path: {exc}")
                vscode_offset = PurePosixPath(".")
            if str(vscode_offset) == ".":
                launch_path = project_path
            else:
                launch_path = project_path / str(vscode_offset)
            subprocess_run([code, str(launch_path)])
        else:
            print("[spawn_task] code.cmd not found on PATH.", file=sys.stderr)

    print(f"\nWorktree created at {project_path} on branch {branch_name}")
    print(f"Task: {task_title}")
    if args.vscode:
        print("Run mill-start in the new VS Code window to continue planning.")
    else:
        print("Run mill-terminal from the parent terminal (python _millhouse/mill-terminal.py) to open a Claude Code session.")

    # Emit the project path as the final stdout line (parity with PS1)
    print(str(project_path))
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_description(body: str, fallback: str) -> str:
    """Extract a task description from body text.

    Handles both bullet-list and prose-paragraph forms (Fix C).
    For bullets, joins the bullet content lines.
    For prose, uses the body verbatim (stripped).
    """
    if not body:
        return fallback

    # Try bullet extraction first
    bullet_lines = []
    for line in body.splitlines():
        # Match bullet items, skip tag lines
        m = re.match(r"^\s*- (.+)$", line)
        if m and not re.match(r"^\s*- tags:", line):
            bullet_lines.append(m.group(1).strip())

    if bullet_lines:
        return "\n".join(bullet_lines)

    # Prose body — return stripped
    return body.strip()


def _claim_task(task):
    """Return a copy of the task with phase changed to 'active'."""
    import dataclasses
    return dataclasses.replace(task, phase="active")


def _read_branch_prefix(config_path: Path) -> str:
    """Read branch-prefix from config.yaml."""
    try:
        text = config_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            m = re.match(r"^\s*branch-prefix:\s*(.+)$", line)
            if m:
                val = m.group(1).strip()
                if val not in ("~", "null", '""', "''"):
                    return val.strip("'\"")
    except Exception:
        pass
    return ""


def _write_handoff(
    handoff_path: Path,
    task_title: str,
    task_description: str,
    parent_branch: str,
    root: Path,
    config_path: Path,
) -> None:
    """Write _millhouse/handoff.md."""
    verify_cmd = "N/A"
    dev_server_cmd = "N/A"
    try:
        text = config_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            m = re.match(r"^\s*verify:\s*(.+)$", line)
            if m:
                verify_cmd = m.group(1).strip()
            m = re.match(r"^\s*dev-server:\s*(.+)$", line)
            if m:
                dev_server_cmd = m.group(1).strip()
    except Exception:
        pass

    discussion_summary = "\n    ".join(task_description.splitlines())

    content = (
        f"# Handoff: {task_title}\n"
        f"\n"
        f"## Issue\n"
        f"{task_title}\n"
        f"\n"
        f"## Parent\n"
        f"Branch: {parent_branch}\n"
        f"Worktree: {root}\n"
        f"\n"
        f"## Discussion Summary\n"
        f"{discussion_summary}\n"
        f"\n"
        f"## Config\n"
        f"- Verify: {verify_cmd}\n"
        f"- Dev server: {dev_server_cmd}\n"
    )
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(content, encoding="utf-8", newline="\n")


def _write_status(
    status_path: Path,
    task_title: str,
    task_description: str,
    parent_branch: str,
) -> None:
    """Write _millhouse/task/status.md using the status template shape."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Indent task_description for YAML block scalar
    desc_lines = task_description.splitlines()
    desc_indented = "\n  ".join(desc_lines)

    content = (
        f"# Status\n"
        f"\n"
        f"```yaml\n"
        f"task: {task_title}\n"
        f"phase: discussing\n"
        f"parent: {parent_branch}\n"
        f"task_description: |\n"
        f"  {desc_indented}\n"
        f"```\n"
        f"\n"
        f"## Timeline\n"
        f"\n"
        f"```text\n"
        f"discussing              {ts}\n"
        f"```\n"
    )
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(content, encoding="utf-8", newline="\n")


# Color palette for worktree title bars. Round-robin from this list.
# The first entry (green) is reserved for the main worktree; child worktrees
# filter it out in `_pick_worktree_color`. See mill-setup/SKILL.md for the
# main-is-always-green invariant.
_WORKTREE_COLOR_PALETTE = [
    "#2d7d46",  # green (main worktree only)
    "#7d2d6b",  # purple
    "#2d4f7d",  # blue
    "#7d5c2d",  # yellow
    "#6b2d2d",  # red
    "#2d6b6b",  # cyan
    "#4a2d7d",  # indigo
    "#7d462d",  # orange
]

# The main worktree is always green. Child worktrees exclude it from their
# rotation so the developer can tell a child from the main at a glance.
_MAIN_WORKTREE_COLOR = "#2d7d46"

# Named view of _WORKTREE_COLOR_PALETTE — the same source of truth, keyed
# by human-readable color names. Used by the `mill-color` entrypoint for
# ad-hoc worktree color overrides.
WORKTREE_COLOR_NAME_TO_HEX: dict[str, str] = {
    "green":  "#2d7d46",
    "purple": "#7d2d6b",
    "blue":   "#2d4f7d",
    "yellow": "#7d5c2d",
    "red":    "#6b2d2d",
    "cyan":   "#2d6b6b",
    "indigo": "#4a2d7d",
    "orange": "#7d462d",
}


def _read_vscode_color(vscode_settings_path: Path) -> str | None:
    """Read titleBar.activeBackground hex value from a .vscode/settings.json file.

    Returns the hex string if found, None otherwise.
    """
    try:
        text = vscode_settings_path.read_text(encoding="utf-8")
        import json
        data = json.loads(text)
        customizations = data.get("workbench.colorCustomizations", {})
        return customizations.get("titleBar.activeBackground")
    except Exception:
        return None


def _pick_worktree_color(worktrees_dir: Path) -> str:
    """Pick the first non-green palette color not used by any sibling worktree.

    Green (`_MAIN_WORKTREE_COLOR`) is reserved for the main worktree and
    is always excluded from the child palette — even if no sibling is
    currently using it. Scans `.vscode/settings.json` in each directory
    under ``worktrees_dir``. If every non-green color is in use, wraps
    around to the first non-green color (purple).
    """
    used_colors: set[str] = set()
    if worktrees_dir.exists():
        for entry in worktrees_dir.iterdir():
            if not entry.is_dir():
                continue
            settings_path = entry / ".vscode" / "settings.json"
            color = _read_vscode_color(settings_path)
            if color:
                used_colors.add(color.lower())

    non_green_palette = [c for c in _WORKTREE_COLOR_PALETTE
                         if c.lower() != _MAIN_WORKTREE_COLOR.lower()]

    for color in non_green_palette:
        if color.lower() not in used_colors:
            return color

    # All non-green colors in use — wrap to first non-green (never green).
    return non_green_palette[0]


def _write_vscode_settings(
    project_in_worktree: Path,
    slug: str,
    repo_root: Path,
    config_path: Path,
    worktrees_dir: Path | None = None,
) -> None:
    """Write .vscode/settings.json under ``project_in_worktree`` with a unique color.

    ``project_in_worktree`` is the mill-project root inside the new worktree
    (git toplevel in flat layouts; git toplevel + nested_offset in nested
    layouts). ``worktrees_dir`` is the git-level directory containing all
    sibling worktrees — used for color-scanning. If omitted, falls back to
    ``project_in_worktree.parent`` for backwards compatibility with existing
    callers/tests exercising the helper in a flat-layout temp directory.

    Idempotent — skips if .vscode/settings.json already exists.
    """
    import json

    vscode_dir = project_in_worktree / ".vscode"
    settings_path = vscode_dir / "settings.json"

    if settings_path.exists():
        return

    # Read short-name from config
    short_name = slug
    try:
        text = config_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            m = re.match(r"^\s*short-name:\s*(.+)$", line)
            if m:
                val = m.group(1).strip().strip("'\"")
                if val not in ("~", "null", ""):
                    short_name = val
                    break
    except Exception:
        pass

    # Read template
    template_path = repo_root / "plugins" / "mill" / "templates" / "vscode-settings.json"
    if template_path.exists():
        template_text = template_path.read_text(encoding="utf-8")
    else:
        # Fallback inline template
        template_text = json.dumps({
            "workbench.colorCustomizations": {
                "titleBar.activeBackground": "<COLOR_HEX>",
                "titleBar.activeForeground": "#ffffff",
                "titleBar.inactiveBackground": "<COLOR_HEX>",
                "titleBar.inactiveForeground": "#ffffffaa",
            },
            "window.title": "<SHORT_NAME>: <SLUG>",
        }, indent=4) + "\n"

    # Pick a color — scan siblings in the explicit git-level worktrees_dir
    # when available; otherwise fall back to project_in_worktree.parent.
    _worktrees_dir = worktrees_dir if worktrees_dir is not None else project_in_worktree.parent
    color = _pick_worktree_color(_worktrees_dir)

    # Substitute tokens
    content = template_text
    content = content.replace("<COLOR_HEX>", color)
    content = content.replace("<SHORT_NAME>", short_name)
    content = content.replace("<SLUG>", slug)

    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(content, encoding="utf-8", newline="\n")


def write_vscode_settings_with_color(
    worktree_path: Path,
    color_hex: str,
    slug: str,
    short_name: str,
) -> Path:
    """Write `.vscode/settings.json` under `worktree_path` using an explicit color.

    Unlike `_write_vscode_settings`, which auto-picks a sibling-avoiding color,
    this helper accepts the hex color directly. Used by the `mill-color`
    entrypoint for ad-hoc overrides. Overwrites any existing settings.json
    (explicit user action — no backup, no idempotency skip).

    Returns the path to the written settings.json.
    """
    import json

    vscode_dir = worktree_path / ".vscode"
    settings_path = vscode_dir / "settings.json"

    # Prefer the template if available in the repo layout (parent/plugins/mill/templates).
    template_path = None
    for ancestor in [worktree_path, *worktree_path.parents]:
        candidate = ancestor / "plugins" / "mill" / "templates" / "vscode-settings.json"
        if candidate.exists():
            template_path = candidate
            break

    if template_path is not None:
        template_text = template_path.read_text(encoding="utf-8")
    else:
        template_text = json.dumps({
            "workbench.colorCustomizations": {
                "titleBar.activeBackground": "<COLOR_HEX>",
                "titleBar.activeForeground": "#ffffff",
                "titleBar.inactiveBackground": "<COLOR_HEX>",
                "titleBar.inactiveForeground": "#ffffffaa",
            },
            "window.title": "<SHORT_NAME>: <SLUG>",
        }, indent=4) + "\n"

    content = (
        template_text
        .replace("<COLOR_HEX>", color_hex)
        .replace("<SHORT_NAME>", short_name)
        .replace("<SLUG>", slug)
    )

    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(content, encoding="utf-8", newline="\n")
    return settings_path


if __name__ == "__main__":
    sys.exit(main())
