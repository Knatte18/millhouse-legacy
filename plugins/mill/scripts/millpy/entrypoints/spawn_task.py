"""
entrypoints/spawn_task.py — Task spawner for millpy (live).

Reads tasks.md, claims the first [>] task (changes to [active]),
creates the worktree, writes status.md, discussion placeholder, and
updates the parent's tasks.md.

Live after W1 Step 10 skill-text flip: called directly by the mill-spawn
skill and by the _millhouse/mill-spawn.cmd forwarding wrapper.

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
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Spawn a worktree for the next [>] task in tasks.md.

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
    from millpy.core.paths import project_root
    from millpy.core.subprocess_util import run as subprocess_run
    from millpy.tasks import tasks_md

    parser = argparse.ArgumentParser(
        prog="spawn_task",
        description="Spawn a worktree for the first [>] task in tasks.md.",
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
    except Exception as exc:
        print(f"[spawn_task] Not in a git repository: {exc}", file=sys.stderr)
        return 1

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
    spawn_task = next((t for t in tasks if t.phase == ">"), None)
    if spawn_task is None:
        print("[spawn_task] No [>] tasks in tasks.md.", file=sys.stderr)
        return 0

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
        print(f"[DryRun] Would change [>] to [active] for task '{task_title}' in tasks.md.")
        print(f"[DryRun] Would create worktree (branch: {branch_name})")
        print(f"[DryRun] Would copy _millhouse/ (excluding task/, scratch/, children/) to new worktree")
        print(f"[DryRun] Would write status.md in new worktree")
        return 0

    # Change [>] to [active] in tasks.md
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

    # Create worktree via git worktree add
    worktrees_dir = root.parent / f"{root.name}.worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    project_path = worktrees_dir / slug

    result = git(
        ["worktree", "add", "-b", branch_name, str(project_path)],
        cwd=root,
    )
    if result.returncode != 0:
        print(f"[spawn_task] git worktree add failed: {result.stderr}", file=sys.stderr)
        return 1

    log("spawn_task", f"Worktree created at {project_path}")

    # Write .vscode/settings.json with a unique worktree color
    _write_vscode_settings(project_path, slug, root, config_path)

    # Copy _millhouse/ (excluding task/, scratch/, children/)
    src_millhouse = root / "_millhouse"
    dst_millhouse = project_path / "_millhouse"
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
    (project_path / "_millhouse" / "scratch" / "reviews").mkdir(parents=True, exist_ok=True)
    (project_path / "_millhouse" / "task" / "reviews").mkdir(parents=True, exist_ok=True)

    # Write status.md
    status_path = project_path / "_millhouse" / "task" / "status.md"
    _write_status(status_path, task_title, task_description, parent_branch)

    # Write discussion placeholder
    discussion_path = project_path / "_millhouse" / "task" / "discussion.md"
    _write_discussion_placeholder(discussion_path, task_title)

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

    # Open VS Code if requested
    if args.vscode:
        code = shutil.which("code.cmd") or shutil.which("code")
        if code:
            subprocess_run([code, str(project_path)])
        else:
            print("[spawn_task] code.cmd not found on PATH.", file=sys.stderr)

    print(f"\nWorktree created at {project_path} on branch {branch_name}")
    print(f"Task: {task_title}")
    if args.vscode:
        print("Run mill-start in the new VS Code window to continue planning.")
    else:
        print("Run mill-terminal from the parent terminal (_millhouse/mill-terminal.cmd or python plugins/mill/scripts/open_terminal.py) to open a Claude Code session.")

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


def _write_discussion_placeholder(discussion_path: Path, task_title: str) -> None:
    """Write a placeholder discussion.md."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = (
        f"# Discussion: {task_title}\n"
        f"\n"
        f"_Generated {ts}_\n"
        f"\n"
        f"## Context\n"
        f"\n"
        f"(Fill in context here before running mill-start)\n"
    )
    discussion_path.write_text(content, encoding="utf-8", newline="\n")


# Color palette for worktree title bars. Round-robin from this list.
_WORKTREE_COLOR_PALETTE = [
    "#2d7d46",  # green
    "#7d2d6b",  # purple
    "#2d4f7d",  # blue
    "#7d5c2d",  # yellow
    "#6b2d2d",  # red
    "#2d6b6b",  # cyan
    "#4a2d7d",  # indigo
    "#7d462d",  # orange
]


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
    """Pick the first color from the palette not used by any sibling worktree.

    Scans `.vscode/settings.json` in each directory under ``worktrees_dir``.
    If all colors are in use, wraps around to the first color in the palette.
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

    for color in _WORKTREE_COLOR_PALETTE:
        if color.lower() not in used_colors:
            return color

    # All colors in use — wrap around
    return _WORKTREE_COLOR_PALETTE[0]


def _write_vscode_settings(
    project_path: Path,
    slug: str,
    repo_root: Path,
    config_path: Path,
) -> None:
    """Write .vscode/settings.json in the new worktree with a unique color.

    Idempotent — skips if .vscode/settings.json already exists.
    """
    import json

    vscode_dir = project_path / ".vscode"
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

    # Pick a color
    worktrees_dir = project_path.parent
    color = _pick_worktree_color(worktrees_dir)

    # Substitute tokens
    content = template_text
    content = content.replace("<COLOR_HEX>", color)
    content = content.replace("<SHORT_NAME>", short_name)
    content = content.replace("<SLUG>", slug)

    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
