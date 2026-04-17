"""Contract tests for millpy.entrypoints.spawn_task.

Business logic is already covered by tests/tasks/. This file exercises
the entrypoint's CLI contract — argparse boundary behaviour, missing
required args, the "not in a git repo" error path, and worktree color logic.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from millpy.entrypoints import spawn_task


# ---------------------------------------------------------------------------
# Integration-test helpers (flat + nested layouts)
# ---------------------------------------------------------------------------

def _init_repo_with_commit(path: Path) -> None:
    """git init + a single empty commit so `git worktree add` has a base ref."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    # The commit performed by spawn_task itself runs under the current
    # process env, so configure the repo's own user so that any commit
    # invoked inside spawn_task.main() succeeds too.
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


def _write_millhouse_project(project_root_dir: Path) -> None:
    """Create a minimal _millhouse/config.yaml and a tasks.md with one [>] task."""
    (project_root_dir / "_millhouse").mkdir(parents=True, exist_ok=True)
    (project_root_dir / "_millhouse" / "config.yaml").write_text(
        "repo:\n  short-name: \"t\"\n  branch-prefix: ~\n",
        encoding="utf-8",
    )
    (project_root_dir / "tasks.md").write_text(
        "# Tasks\n\n## [>] Ready Task\nA short description.\n",
        encoding="utf-8",
    )


def _run_spawn_and_get_project_path(
    monkeypatch, capsys, cwd: Path, repo_dir: Path
) -> Path:
    """Invoke spawn_task.main([]) from ``cwd`` and return the project_path printed on stdout."""
    monkeypatch.chdir(cwd)
    # spawn_task.main() commits tasks.md in the parent repo. Make the commit
    # step a no-op on failure-tolerance: the entrypoint itself already
    # swallows git commit/push exceptions.
    exit_code = spawn_task.main([])
    assert exit_code == 0
    out = capsys.readouterr().out.splitlines()
    # Last line of stdout is the project_path — parity with PS1 predecessor.
    return Path(out[-1])


# ---------------------------------------------------------------------------


def test_main_with_no_git_repo_exits_nonzero(tmp_path, monkeypatch):
    """spawn_task invoked outside a git repo returns non-zero with a clear stderr."""
    monkeypatch.chdir(tmp_path)
    exit_code = spawn_task.main(["--dry-run"])
    assert exit_code != 0


def test_main_missing_config_exits_nonzero(tmp_path, monkeypatch, capsys):
    """Inside a git repo but with no _millhouse/config.yaml, spawn_task must fail
    with a clear stderr mentioning mill-setup."""
    import subprocess
    import os

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    monkeypatch.chdir(tmp_path)

    exit_code = spawn_task.main([])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "mill-setup" in captured.err.lower() or "mill-setup" in captured.out.lower()


# ---------------------------------------------------------------------------
# Worktree color helpers
# ---------------------------------------------------------------------------

class TestPickWorktreeColor:
    """Green is reserved for the main worktree. Child worktrees always
    pick the first NON-green palette entry. See test_pick_worktree_color.py
    for the green-exclusion invariant tests.
    """

    def _first_non_green(self):
        return next(c for c in spawn_task._WORKTREE_COLOR_PALETTE
                    if c.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower())

    def test_returns_first_non_green_color_when_no_siblings(self, tmp_path):
        """When worktrees_dir is empty, returns the first non-green palette color."""
        color = spawn_task._pick_worktree_color(tmp_path)
        assert color == self._first_non_green()

    def test_skips_color_used_by_sibling_worktree(self, tmp_path):
        """Skips a color already used by a sibling worktree's .vscode/settings.json."""
        first_non_green = self._first_non_green()
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        vscode = sibling / ".vscode"
        vscode.mkdir()
        (vscode / "settings.json").write_text(
            json.dumps({
                "workbench.colorCustomizations": {
                    "titleBar.activeBackground": first_non_green,
                }
            }),
            encoding="utf-8",
        )

        # Skip the first non-green (in use) → return the next non-green.
        color = spawn_task._pick_worktree_color(tmp_path)
        non_green_palette = [c for c in spawn_task._WORKTREE_COLOR_PALETTE
                             if c.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower()]
        assert color == non_green_palette[1]

    def test_wraps_around_when_all_non_green_colors_in_use(self, tmp_path):
        """When all non-green colors are in use, wraps to the first non-green."""
        non_green_palette = [c for c in spawn_task._WORKTREE_COLOR_PALETTE
                             if c.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower()]
        for index, color in enumerate(non_green_palette):
            sibling = tmp_path / f"sibling-{index}"
            sibling.mkdir()
            vscode = sibling / ".vscode"
            vscode.mkdir()
            (vscode / "settings.json").write_text(
                json.dumps({
                    "workbench.colorCustomizations": {
                        "titleBar.activeBackground": color,
                    }
                }),
                encoding="utf-8",
            )

        color = spawn_task._pick_worktree_color(tmp_path)
        assert color == non_green_palette[0]
        assert color.lower() != spawn_task._MAIN_WORKTREE_COLOR.lower()

    def test_missing_worktrees_dir_returns_first_non_green(self, tmp_path):
        """When worktrees_dir does not exist, returns the first non-green palette color."""
        nonexistent = tmp_path / "does-not-exist"
        color = spawn_task._pick_worktree_color(nonexistent)
        assert color == self._first_non_green()


class TestWriteVscodeSettings:
    def _make_repo_root(self, tmp_path: Path, short_name: str = "myrepo") -> Path:
        """Create a minimal repo root with config.yaml."""
        (tmp_path / "_millhouse").mkdir(parents=True, exist_ok=True)
        config = tmp_path / "_millhouse" / "config.yaml"
        config.write_text(
            f"repo:\n  short-name: \"{short_name}\"\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_creates_vscode_settings_with_color(self, tmp_path):
        """Creates .vscode/settings.json in new worktree with a color from the palette."""
        repo_root = self._make_repo_root(tmp_path / "repo")
        worktree = tmp_path / "worktrees" / "my-task"
        worktree.mkdir(parents=True)

        spawn_task._write_vscode_settings(
            worktree, "my-task", repo_root, repo_root / "_millhouse" / "config.yaml"
        )

        settings_path = worktree / ".vscode" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        color = data["workbench.colorCustomizations"]["titleBar.activeBackground"]
        assert color in spawn_task._WORKTREE_COLOR_PALETTE

    def test_skips_when_settings_already_exists(self, tmp_path):
        """Does not overwrite an existing .vscode/settings.json."""
        repo_root = self._make_repo_root(tmp_path / "repo")
        worktree = tmp_path / "worktrees" / "my-task"
        vscode = worktree / ".vscode"
        vscode.mkdir(parents=True)
        existing = vscode / "settings.json"
        existing.write_text('{"existing": true}', encoding="utf-8")

        spawn_task._write_vscode_settings(
            worktree, "my-task", repo_root, repo_root / "_millhouse" / "config.yaml"
        )

        data = json.loads(existing.read_text(encoding="utf-8"))
        assert data == {"existing": True}

    def test_window_title_contains_slug(self, tmp_path):
        """window.title in the written settings contains the task slug."""
        repo_root = self._make_repo_root(tmp_path / "repo", short_name="proj")
        worktree = tmp_path / "worktrees" / "add-feature"
        worktree.mkdir(parents=True)

        spawn_task._write_vscode_settings(
            worktree, "add-feature", repo_root, repo_root / "_millhouse" / "config.yaml"
        )

        data = json.loads((worktree / ".vscode" / "settings.json").read_text(encoding="utf-8"))
        assert "add-feature" in data["window.title"]


# ---------------------------------------------------------------------------
# Layout-aware integration tests (flat vs nested mill project)
# ---------------------------------------------------------------------------

class TestWorktreeLayout:
    def test_flat_layout_worktrees_dir_is_sibling_of_repo_and_project_root(
        self, tmp_path, monkeypatch, capsys
    ):
        """Flat layout: worktrees_dir is sibling of git root; _millhouse lives at worktree toplevel."""
        git_root = tmp_path / "myrepo"
        git_root.mkdir()
        _init_repo_with_commit(git_root)
        _write_millhouse_project(git_root)

        project_path = _run_spawn_and_get_project_path(
            monkeypatch, capsys, cwd=git_root, repo_dir=git_root
        )

        assert project_path.parent == (tmp_path / "myrepo.worktrees").resolve()
        assert (project_path / "_millhouse" / "task" / "status.md").exists()

    def test_nested_layout_worktrees_dir_is_sibling_of_git_root(
        self, tmp_path, monkeypatch, capsys
    ):
        """Nested mill project: worktrees_dir must sit next to the git root, not the project root."""
        git_root = tmp_path / "myrepo"
        git_root.mkdir()
        _init_repo_with_commit(git_root)

        project_dir = git_root / "projects" / "sub"
        project_dir.mkdir(parents=True)
        _write_millhouse_project(project_dir)

        project_path = _run_spawn_and_get_project_path(
            monkeypatch, capsys, cwd=project_dir, repo_dir=git_root
        )

        assert project_path.parent == (tmp_path / "myrepo.worktrees").resolve()

    def test_nested_layout_millhouse_written_under_project_offset(
        self, tmp_path, monkeypatch, capsys
    ):
        """Nested mill project: the worktree's _millhouse lives under projects/sub, not the git toplevel."""
        git_root = tmp_path / "myrepo"
        git_root.mkdir()
        _init_repo_with_commit(git_root)

        project_dir = git_root / "projects" / "sub"
        project_dir.mkdir(parents=True)
        _write_millhouse_project(project_dir)

        project_path = _run_spawn_and_get_project_path(
            monkeypatch, capsys, cwd=project_dir, repo_dir=git_root
        )

        assert (project_path / "projects" / "sub" / "_millhouse" / "task" / "status.md").exists()
        assert not (project_path / "_millhouse").exists()

    def test_nested_layout_vscode_settings_written_at_project_offset(
        self, tmp_path, monkeypatch, capsys
    ):
        """.vscode/settings.json also lives under the project offset, not the worktree toplevel."""
        git_root = tmp_path / "myrepo"
        git_root.mkdir()
        _init_repo_with_commit(git_root)

        project_dir = git_root / "projects" / "sub"
        project_dir.mkdir(parents=True)
        _write_millhouse_project(project_dir)

        project_path = _run_spawn_and_get_project_path(
            monkeypatch, capsys, cwd=project_dir, repo_dir=git_root
        )

        assert (project_path / "projects" / "sub" / ".vscode" / "settings.json").exists()

    def test_vscode_flag_opens_cwd_subfolder_in_new_worktree(
        self, tmp_path, monkeypatch, capsys
    ):
        """--vscode with cwd in a subfolder opens the mirrored subfolder in the child worktree."""
        git_root = tmp_path / "myrepo"
        git_root.mkdir()
        _init_repo_with_commit(git_root)
        _write_millhouse_project(git_root)
        subfolder = git_root / "plugins" / "mill" / "scripts"
        subfolder.mkdir(parents=True)

        captured_calls: list[list[str]] = []
        real_run = __import__("millpy.core.subprocess_util", fromlist=["run"]).run

        def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
            if argv and argv[0] == "git":
                return real_run(argv, cwd=cwd, **kwargs)
            captured_calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        monkeypatch.setattr(
            "millpy.entrypoints.spawn_task.shutil.which",
            lambda name: "/fake/code.cmd" if name in ("code.cmd", "code") else None,
        )
        monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
        monkeypatch.chdir(subfolder)

        exit_code = spawn_task.main(["--vscode"])
        assert exit_code == 0

        out_lines = capsys.readouterr().out.splitlines()
        project_path = Path(out_lines[-1])

        code_calls = [c for c in captured_calls if c and "code" in str(c[0]).lower()]
        assert len(code_calls) == 1
        launch_arg = Path(code_calls[0][1]).resolve()
        expected = (project_path / "plugins" / "mill" / "scripts").resolve()
        assert launch_arg == expected

    def test_vscode_flag_falls_back_to_project_path_when_cwd_offset_raises(
        self, tmp_path, monkeypatch, capsys
    ):
        """If cwd_offset() raises inside the --vscode launch, fall back to opening project_path."""
        git_root = tmp_path / "myrepo"
        git_root.mkdir()
        _init_repo_with_commit(git_root)
        _write_millhouse_project(git_root)

        captured_calls: list[list[str]] = []
        real_run = __import__("millpy.core.subprocess_util", fromlist=["run"]).run
        real_cwd_offset = __import__(
            "millpy.core.paths", fromlist=["cwd_offset"]
        ).cwd_offset
        raise_next = {"pending": False}

        def _fake_cwd_offset(*args, **kwargs):
            # Allow the first cwd_offset call (used elsewhere, if any); the
            # --vscode launch only calls it after `git worktree add`, so we
            # arm the raise just before the entrypoint reaches that block by
            # flipping the flag on the first fake invocation.
            if raise_next["pending"]:
                raise ValueError("simulated cwd_offset failure")
            return real_cwd_offset(*args, **kwargs)

        def _fake_subprocess_run(argv, *args, cwd=None, **kwargs):
            if argv and argv[0] == "git":
                return real_run(argv, cwd=cwd, **kwargs)
            # First non-git subprocess call is the `code` launch — by that
            # point we want cwd_offset to raise. Flip the flag just before.
            raise_next["pending"] = True
            captured_calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        # Patch cwd_offset at its import site inside spawn_task.main's local scope
        # (the function imports it as `from millpy.core.paths import cwd_offset`).
        monkeypatch.setattr("millpy.core.paths.cwd_offset", _fake_cwd_offset)
        monkeypatch.setattr(
            "millpy.entrypoints.spawn_task.shutil.which",
            lambda name: "/fake/code.cmd" if name in ("code.cmd", "code") else None,
        )
        monkeypatch.setattr("millpy.core.subprocess_util.run", _fake_subprocess_run)
        monkeypatch.chdir(git_root)

        # Arm the raise immediately — there are no pre-launch cwd_offset calls
        # in the flat-layout happy path, so raising from the start is fine.
        raise_next["pending"] = True

        exit_code = spawn_task.main(["--vscode"])
        assert exit_code == 0

        out_lines = capsys.readouterr().out.splitlines()
        project_path = Path(out_lines[-1])

        code_calls = [c for c in captured_calls if c and "code" in str(c[0]).lower()]
        assert len(code_calls) == 1
        launch_arg = Path(code_calls[0][1]).resolve()
        assert launch_arg == project_path.resolve()
