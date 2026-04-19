"""Tests for millpy.entrypoints.notify.

Covers:
- Happy: toast enabled, platform detected, subprocess called with correct args
- Happy: toast disabled in config → no subprocess call
- Edge: config file missing → defaults to toast enabled
- Error: subprocess raises → warning on stderr, exits 0
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config_with_toast(enabled: bool, tmp_path: Path) -> Path:
    """Write a minimal .millhouse/config.yaml with toast.enabled set."""
    config_dir = tmp_path / ".millhouse"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    enabled_str = "true" if enabled else "false"
    config_path.write_text(
        f"notifications:\n  toast:\n    enabled: {enabled_str}\n",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Toast enabled — notification sent
# ---------------------------------------------------------------------------

class TestToastEnabled:
    def test_windows_calls_powershell_burnttoast(self, tmp_path, monkeypatch, capsys):
        """On Windows, send_notification calls PowerShell New-BurntToastNotification."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "win32")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            exit_code = notify.main([
                "--event", "COMPLETE",
                "--branch", "my-branch",
                "--detail", "done",
                "--urgency", "info",
            ], project_root_override=root)

        assert exit_code == 0
        assert mock_run.called
        cmd_str = " ".join(mock_run.call_args[0][0])
        assert "New-BurntToastNotification" in cmd_str

    def test_macos_calls_osascript(self, tmp_path, monkeypatch, capsys):
        """On macOS, send_notification calls osascript."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "darwin")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            exit_code = notify.main([
                "--event", "COMPLETE",
                "--branch", "my-branch",
                "--detail", "done",
            ], project_root_override=root)

        assert exit_code == 0
        assert mock_run.called
        cmd_str = " ".join(mock_run.call_args[0][0])
        assert "osascript" in cmd_str

    def test_linux_calls_notify_send(self, tmp_path, monkeypatch, capsys):
        """On Linux, send_notification calls notify-send."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "linux")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            exit_code = notify.main([
                "--event", "COMPLETE",
                "--branch", "my-branch",
                "--detail", "done",
            ], project_root_override=root)

        assert exit_code == 0
        assert mock_run.called
        cmd_str = " ".join(mock_run.call_args[0][0])
        assert "notify-send" in cmd_str

    def test_title_contains_branch_and_event(self, tmp_path, monkeypatch):
        """Notification title includes branch and event."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "linux")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            notify.main([
                "--event", "BLOCKED",
                "--branch", "feat-xyz",
                "--detail", "reason",
            ], project_root_override=root)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "feat-xyz" in cmd_str
        assert "BLOCKED" in cmd_str


# ---------------------------------------------------------------------------
# Toast disabled
# ---------------------------------------------------------------------------

class TestToastDisabled:
    def test_no_subprocess_called_when_toast_disabled(self, tmp_path, monkeypatch):
        """When toast.enabled is false in config, no subprocess call is made."""
        root = _config_with_toast(enabled=False, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "linux")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            exit_code = notify.main([
                "--event", "COMPLETE",
                "--branch", "my-branch",
                "--detail", "done",
            ], project_root_override=root)

        assert exit_code == 0
        assert not mock_run.called


# ---------------------------------------------------------------------------
# Config missing — default to enabled
# ---------------------------------------------------------------------------

class TestConfigMissing:
    def test_missing_config_defaults_to_toast_enabled(self, tmp_path, monkeypatch):
        """When config.yaml is absent, toast is enabled by default."""
        # tmp_path has no .millhouse/config.yaml
        monkeypatch.setattr("sys.platform", "linux")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            exit_code = notify.main([
                "--event", "COMPLETE",
                "--branch", "my-branch",
                "--detail", "done",
            ], project_root_override=tmp_path)

        assert exit_code == 0
        assert mock_run.called


# ---------------------------------------------------------------------------
# Subprocess failure — warning on stderr, exit 0
# ---------------------------------------------------------------------------

class TestSubprocessFailure:
    def test_subprocess_returncode_nonzero_exits_zero_with_stderr_warning(
        self, tmp_path, monkeypatch, capsys
    ):
        """Non-zero subprocess returncode → warning on stderr, exits 0."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "linux")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            exit_code = notify.main([
                "--event", "COMPLETE",
                "--branch", "my-branch",
                "--detail", "done",
            ], project_root_override=root)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()

    def test_subprocess_raises_exception_exits_zero_with_stderr_warning(
        self, tmp_path, monkeypatch, capsys
    ):
        """Subprocess raising an exception → warning on stderr, exits 0."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "linux")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("notify-send not found")
            exit_code = notify.main([
                "--event", "COMPLETE",
                "--branch", "my-branch",
                "--detail", "done",
            ], project_root_override=root)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()


# ---------------------------------------------------------------------------
# Input sanitization
# ---------------------------------------------------------------------------

class TestInputSanitization:
    def test_shell_breaking_chars_stripped_from_inputs(self, tmp_path, monkeypatch):
        """Characters that break shell quoting are stripped from inputs."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)
        monkeypatch.setattr("sys.platform", "linux")

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            notify.main([
                "--event", 'COMPLETE"$evil`',
                "--branch", "my-branch",
                "--detail", "done",
            ], project_root_override=root)

        cmd_str = " ".join(mock_run.call_args[0][0])
        assert '"' not in cmd_str
        assert "$" not in cmd_str
        assert "`" not in cmd_str


# ---------------------------------------------------------------------------
# Missing --event exits 0 with warning
# ---------------------------------------------------------------------------

class TestMissingEvent:
    def test_missing_event_exits_zero_with_warning(self, tmp_path, monkeypatch, capsys):
        """When --event is missing, exits 0 with a warning on stderr."""
        root = _config_with_toast(enabled=True, tmp_path=tmp_path)

        from millpy.entrypoints import notify

        with patch("millpy.entrypoints.notify.subprocess.run"):
            exit_code = notify.main([
                "--branch", "my-branch",
            ], project_root_override=root)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "event" in captured.err.lower()
