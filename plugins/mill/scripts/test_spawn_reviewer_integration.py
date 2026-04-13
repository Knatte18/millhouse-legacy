"""Integration tests for spawn-reviewer.py using a stub spawn-agent backend.

All tests use SPAWN_AGENT_PATH env var to point spawn_reviewer.py at the stub
backend. No real LLM is called. All tests should complete in under 30s.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

# Ensure spawn_reviewer is importable
sys.path.insert(0, os.path.dirname(__file__))

# Path to the stub backend
_STUB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'test-fixtures', 'stub-spawn-agent.ps1')
)

# Path to spawn-reviewer entry point
_SPAWN_REVIEWER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'spawn-reviewer.py')
)


def _run_spawn_reviewer(args: list, config_text: str, env_extra: dict = None) -> subprocess.CompletedProcess:
    """Run spawn-reviewer.py as a subprocess with the stub backend wired."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False,
                                     encoding='utf-8') as f:
        f.write(config_text)
        config_path = f.name
    try:
        env = os.environ.copy()
        env['SPAWN_AGENT_PATH'] = _STUB_PATH
        if env_extra:
            env.update(env_extra)
        cmd = [sys.executable, _SPAWN_REVIEWER] + args + ['--config', config_path]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, env=env,
        )
        return result
    finally:
        try:
            os.unlink(config_path)
        except Exception:
            pass


def _make_prompt_file(content: str) -> str:
    """Write content to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                     encoding='utf-8') as f:
        f.write(content)
        return f.name


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_TOOL_USE_CONFIG = textwrap.dedent("""\
    reviewers:
      single-sonnet:
        worker-model: sonnet
        worker-count: 1
        dispatch: tool-use

    review-modules:
      code:
        default: single-sonnet
      plan:
        default: single-sonnet
      discussion:
        default: single-sonnet
""")

_BULK_N3_CONFIG = textwrap.dedent("""\
    reviewers:
      ensemble-stub3:
        worker-model: sonnet
        worker-count: 3
        dispatch: bulk
        handler-model: sonnet
        prompt-template: plugins/mill/doc/modules/code-review-bulk.md
        max-bundle-chars: 999999

    review-modules:
      code:
        default: ensemble-stub3
      plan:
        default: ensemble-stub3
      discussion:
        default: ensemble-stub3
""")

_BOTGATE_CONFIG_TMPL = textwrap.dedent("""\
    reviewers:
      botgate-recipe:
        worker-model: stub-fail-botgate
        worker-count: 3
        dispatch: bulk
        handler-model: sonnet
        prompt-template: plugins/mill/doc/modules/code-review-bulk.md
        max-bundle-chars: 999999
        fallback: fallback-recipe
      fallback-recipe:
        worker-model: sonnet
        worker-count: 1
        dispatch: tool-use

    review-modules:
      code:
        default: botgate-recipe
      plan:
        default: botgate-recipe
      discussion:
        default: fallback-recipe
""")

_BOTGATE_NO_FALLBACK_CONFIG = textwrap.dedent("""\
    reviewers:
      botgate-no-fallback:
        worker-model: stub-fail-botgate
        worker-count: 3
        dispatch: bulk
        handler-model: sonnet
        prompt-template: plugins/mill/doc/modules/code-review-bulk.md
        max-bundle-chars: 999999

    review-modules:
      code:
        default: botgate-no-fallback
      plan:
        default: botgate-no-fallback
      discussion:
        default: botgate-no-fallback
""")

_ALL_FAIL_CONFIG = textwrap.dedent("""\
    reviewers:
      all-fail:
        worker-model: stub-fail-429
        worker-count: 3
        dispatch: bulk
        handler-model: sonnet
        prompt-template: plugins/mill/doc/modules/code-review-bulk.md
        max-bundle-chars: 999999

    review-modules:
      code:
        default: all-fail
      plan:
        default: all-fail
      discussion:
        default: all-fail
""")


class TestIntegrationToolUse(unittest.TestCase):
    """Tool-use n=1 degenerate recipe against the stub."""

    def setUp(self):
        self.prompt_file = _make_prompt_file("# Plan review prompt\n(stub)")

    def tearDown(self):
        try:
            os.unlink(self.prompt_file)
        except Exception:
            pass

    def test_tool_use_n1_happy(self):
        """n=1 tool-use recipe: stdout is a valid JSON line with APPROVE verdict."""
        result = _run_spawn_reviewer(
            ['--reviewer-name', 'single-sonnet',
             '--prompt-file', self.prompt_file,
             '--phase', 'plan',
             '--round', '1'],
            _TOOL_USE_CONFIG,
        )
        self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")
        # Parse the JSON line from stdout
        stdout = result.stdout.strip()
        self.assertTrue(stdout, "stdout should not be empty")
        parsed = json.loads(stdout)
        self.assertEqual(parsed['verdict'], 'APPROVE')
        self.assertIn('review_file', parsed)


class TestIntegrationBulkN3(unittest.TestCase):
    """Bulk n=3 ensemble against the stub."""

    def setUp(self):
        self.prompt_file = _make_prompt_file("# Code review prompt\n(stub)")

    def tearDown(self):
        try:
            os.unlink(self.prompt_file)
        except Exception:
            pass

    def test_bulk_n3_all_succeed(self):
        """n=3 bulk ensemble: all 3 workers succeed, handler spawned, final JSON emitted."""
        # The stub handler also returns APPROVE via tool-use path
        # We need a real plan file and git repo for bulk scope gathering.
        # Since we don't have a git repo in the test env, we use plan-review phase
        # which reads from plan_path instead of git diff.
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                         encoding='utf-8') as f:
            f.write("# Plan\n\n## Files\n\n- fake/file.py\n")
            plan_path = f.name
        try:
            # For plan phase with bulk: we need a plan file and the template to exist.
            # The template path in config is relative to git root; use a temp one.
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create the bulk template at the expected relative path
                tmpl_dir = os.path.join(tmpdir, 'plugins', 'mill', 'doc', 'modules')
                os.makedirs(tmpl_dir, exist_ok=True)
                tmpl_path = os.path.join(tmpl_dir, 'code-review-bulk.md')
                with open(tmpl_path, 'w') as tf:
                    tf.write("Round: <ROUND>\nDiff: <DIFF>\nPlan: <PLAN_CONTENT>\n<FILE_BUNDLE>\n")

                # Create a fake file for the bundle
                fake_dir = os.path.join(tmpdir, 'fake')
                os.makedirs(fake_dir, exist_ok=True)
                with open(os.path.join(fake_dir, 'file.py'), 'w') as ff:
                    ff.write("# stub")

                config = _BULK_N3_CONFIG
                result = _run_spawn_reviewer(
                    ['--reviewer-name', 'ensemble-stub3',
                     '--prompt-file', self.prompt_file,
                     '--phase', 'plan',
                     '--round', '1',
                     '--plan-path', plan_path,
                     '--work-dir', tmpdir],
                    config,
                )
            self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")
            stdout = result.stdout.strip()
            parsed = json.loads(stdout)
            self.assertEqual(parsed['verdict'], 'APPROVE')
        finally:
            os.unlink(plan_path)


class TestIntegrationBotGate(unittest.TestCase):
    """Bot-gate path: primary bot-gated, fallback used."""

    def setUp(self):
        self.prompt_file = _make_prompt_file("# prompt\n(stub)")

    def tearDown(self):
        try:
            os.unlink(self.prompt_file)
        except Exception:
            pass

    def test_botgate_triggers_fallback(self):
        """When all 3 workers are bot-gated and fallback=single-sonnet, fallback is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_dir = os.path.join(tmpdir, 'plugins', 'mill', 'doc', 'modules')
            os.makedirs(tmpl_dir, exist_ok=True)
            tmpl_path = os.path.join(tmpl_dir, 'code-review-bulk.md')
            with open(tmpl_path, 'w') as tf:
                tf.write("Round: <ROUND>\n<FILE_BUNDLE>\n")

            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                             encoding='utf-8') as f:
                f.write("# Plan\n\n## Files\n\n- fake.py\n")
                plan_path = f.name
            try:
                fake_file = os.path.join(tmpdir, 'fake.py')
                with open(fake_file, 'w') as ff:
                    ff.write("# stub")

                reviews_dir = os.path.join(tmpdir, '_millhouse', 'scratch', 'reviews')
                os.makedirs(reviews_dir, exist_ok=True)

                result = _run_spawn_reviewer(
                    ['--reviewer-name', 'botgate-recipe',
                     '--prompt-file', self.prompt_file,
                     '--phase', 'plan',
                     '--round', '1',
                     '--plan-path', plan_path,
                     '--work-dir', tmpdir],
                    _BOTGATE_CONFIG_TMPL,
                )
            finally:
                os.unlink(plan_path)

        # The fallback (single-sonnet tool-use) should succeed
        self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")
        stdout = result.stdout.strip()
        parsed = json.loads(stdout)
        self.assertEqual(parsed['verdict'], 'APPROVE')
        # Bot-gate marker should be mentioned in stderr
        self.assertIn('bot', result.stderr.lower())

    def test_botgate_no_fallback_exits_nonzero(self):
        """Bot-gate with no fallback: spawn-reviewer exits non-zero with 'no fallback' message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_dir = os.path.join(tmpdir, 'plugins', 'mill', 'doc', 'modules')
            os.makedirs(tmpl_dir, exist_ok=True)
            tmpl_path = os.path.join(tmpl_dir, 'code-review-bulk.md')
            with open(tmpl_path, 'w') as tf:
                tf.write("Round: <ROUND>\n<FILE_BUNDLE>\n")

            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                             encoding='utf-8') as f:
                f.write("# Plan\n\n## Files\n\n- fake.py\n")
                plan_path = f.name
            try:
                fake_file = os.path.join(tmpdir, 'fake.py')
                with open(fake_file, 'w') as ff:
                    ff.write("# stub")

                result = _run_spawn_reviewer(
                    ['--reviewer-name', 'botgate-no-fallback',
                     '--prompt-file', self.prompt_file,
                     '--phase', 'plan',
                     '--round', '1',
                     '--plan-path', plan_path,
                     '--work-dir', tmpdir],
                    _BOTGATE_NO_FALLBACK_CONFIG,
                )
            finally:
                os.unlink(plan_path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('bot', result.stderr.lower())

    def test_preexisting_botgate_marker_skips_primary(self):
        """Pre-existing bot-gate marker → primary skipped at startup, fallback dispatched directly.

        Uses --phase plan so resolve_reviewer accepts the bulk primary recipe.
        The marker check then swaps to the tool-use fallback before any dispatch,
        so no --plan-path or template files are needed.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-create the session marker so spawn-reviewer sees it on startup
            reviews_dir = os.path.join(tmpdir, '_millhouse', 'scratch', 'reviews')
            os.makedirs(reviews_dir, exist_ok=True)
            marker_path = os.path.join(reviews_dir, 'bot-gated-botgate-recipe.flag')
            with open(marker_path, 'w') as mf:
                mf.write('')

            result = _run_spawn_reviewer(
                ['--reviewer-name', 'botgate-recipe',
                 '--prompt-file', self.prompt_file,
                 '--phase', 'plan',
                 '--round', '1',
                 '--work-dir', tmpdir],
                _BOTGATE_CONFIG_TMPL,
            )

        # Fallback (single-sonnet tool-use) should succeed
        self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")
        stdout = result.stdout.strip()
        parsed = json.loads(stdout)
        self.assertEqual(parsed['verdict'], 'APPROVE')
        # Marker skip message should appear in stderr
        self.assertIn('marker', result.stderr.lower())


class TestIntegrationDegradedFatal(unittest.TestCase):
    """All workers fail → degraded-fatal."""

    def setUp(self):
        self.prompt_file = _make_prompt_file("# prompt\n(stub)")

    def tearDown(self):
        try:
            os.unlink(self.prompt_file)
        except Exception:
            pass

    def test_all_workers_fail(self):
        """3/3 workers rate-limited → exit non-zero with degraded-fatal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_dir = os.path.join(tmpdir, 'plugins', 'mill', 'doc', 'modules')
            os.makedirs(tmpl_dir, exist_ok=True)
            with open(os.path.join(tmpl_dir, 'code-review-bulk.md'), 'w') as tf:
                tf.write("Round: <ROUND>\n<FILE_BUNDLE>\n")

            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                             encoding='utf-8') as f:
                f.write("# Plan\n\n## Files\n\n- fake.py\n")
                plan_path = f.name
            try:
                with open(os.path.join(tmpdir, 'fake.py'), 'w') as ff:
                    ff.write("# stub")

                result = _run_spawn_reviewer(
                    ['--reviewer-name', 'all-fail',
                     '--prompt-file', self.prompt_file,
                     '--phase', 'plan',
                     '--round', '1',
                     '--plan-path', plan_path,
                     '--work-dir', tmpdir],
                    _ALL_FAIL_CONFIG,
                )
            finally:
                os.unlink(plan_path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('degraded', result.stderr.lower())


if __name__ == '__main__':
    unittest.main()
