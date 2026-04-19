"""
entrypoints/notify.py — Best-effort desktop notification for mill skills.

Called by mill-go and mill-merge at specific trigger points.
Reads .millhouse/config.yaml to decide whether toast is enabled.
Always exits 0 — failures warn on stderr, never block the caller.

CLI interface mirrors notify.sh:
  --event    Event name (required)
  --branch   Branch name
  --detail   Detail message
  --urgency  high | info (default: high)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# Characters that break shell quoting in platform commands.
_SHELL_BREAKING_CHARS = '"$\'`\\'


def _sanitize(text: str) -> str:
    """Strip shell-breaking characters from input text."""
    return "".join(ch for ch in text if ch not in _SHELL_BREAKING_CHARS)


def _toast_enabled(project_root: Path) -> bool:
    """Read notifications.toast.enabled from .millhouse/config.yaml.

    Returns True when config is missing, key is absent, or value is true.
    Returns False only when explicitly set to false.
    """
    config_path = project_root / ".millhouse" / "config.yaml"
    if not config_path.exists():
        return True

    try:
        from millpy.core.config import load
        cfg = load(config_path)
    except Exception:
        return True

    notifications = cfg.get("notifications", {})
    if not isinstance(notifications, dict):
        return True
    toast = notifications.get("toast", {})
    if not isinstance(toast, dict):
        return True
    enabled = toast.get("enabled", True)
    if enabled is False:
        return False
    return True


def _send_notification(title: str, detail: str) -> None:
    """Send a desktop notification using the platform-appropriate command.

    On failure (non-zero return code or exception), writes a warning to
    stderr and returns — never raises.
    """
    platform = sys.platform
    try:
        if platform == "win32":
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"New-BurntToastNotification -Text '{title}', '{detail}'",
            ]
        elif platform == "darwin":
            cmd = [
                "osascript",
                "-e",
                f'display notification "{detail}" with title "{title}"',
            ]
        else:
            # Linux and other Unix-like platforms
            cmd = ["notify-send", title, detail]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            sys.stderr.write(
                f"[mill-notify] warning: notification command failed"
                f" (exit {result.returncode})\n"
            )
    except Exception as exc:
        sys.stderr.write(f"[mill-notify] warning: notification command raised: {exc}\n")


def main(
    argv: list[str] | None = None,
    project_root_override: Path | None = None,
) -> int:
    """Send a desktop notification.

    Parameters
    ----------
    argv:
        Argument vector. Defaults to sys.argv[1:].
    project_root_override:
        Override the project root (used in tests to point at a tmp_path).

    Returns
    -------
    int
        Always 0 — failures warn on stderr, never block the caller.
    """
    from millpy.core.log_util import log

    parser = argparse.ArgumentParser(
        prog="notify",
        description="Best-effort desktop notification for mill skills.",
        exit_on_error=False,
    )
    parser.add_argument("--event", default="", help="Event name")
    parser.add_argument("--branch", default="", help="Branch name")
    parser.add_argument("--detail", default="", help="Detail message")
    parser.add_argument("--urgency", default="high", help="Urgency: high | info")

    try:
        args = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return 0

    if not args.event:
        sys.stderr.write("[mill-notify] warning: --event is required\n")
        return 0

    # Resolve project root
    if project_root_override is not None:
        root = project_root_override
    else:
        try:
            from millpy.core.paths import project_root
            root = project_root()
        except Exception as exc:
            sys.stderr.write(
                f"[mill-notify] warning: could not resolve project root: {exc}\n"
            )
            return 0

    if not _toast_enabled(root):
        return 0

    # Sanitize inputs
    safe_event = _sanitize(args.event)
    safe_branch = _sanitize(args.branch)
    safe_detail = _sanitize(args.detail)

    title = f"[mill] {safe_branch} {safe_event}".strip()

    log("notify", f"event={safe_event} branch={safe_branch} urgency={args.urgency}")
    _send_notification(title, safe_detail)

    # Slack placeholder (TODO)
    # URGENCY is intentionally a no-op until Slack is implemented.
    # When enabled, info-level events (completion) skip Slack; high-urgency
    # events (blocked) post to the webhook.

    return 0


if __name__ == "__main__":
    sys.exit(main())
