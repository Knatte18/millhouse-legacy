"""Unit tests for spawn-reviewer.py — Steps 3, 4, 5, 6, 7."""

import os
import sys
import tempfile
import unittest

# Ensure spawn_reviewer is importable from this directory
sys.path.insert(0, os.path.dirname(__file__))

# ============================================================================
# Inline YAML fixtures
# ============================================================================

MINIMAL_CONFIG_YAML = """\
reviewers:
  single-opus:
    worker-model: opus
    worker-count: 1
    dispatch: tool-use
  single-sonnet:
    worker-model: sonnet
    worker-count: 1
    dispatch: tool-use
  sonnet-single-maxeffort:
    worker-model: sonnet
    worker-count: 1
    dispatch: tool-use
  ensemble-gemini3-opus:
    worker-model: gemini-3-pro
    worker-count: 3
    dispatch: bulk
    handler-model: opus
    prompt-template: plugins/mill/doc/modules/code-review-bulk.md
    max-bundle-chars: 200000
    fallback: sonnet-single-maxeffort

review-modules:
  discussion:
    default: single-opus
  plan:
    default: single-sonnet
  code:
    1: ensemble-gemini3-opus
    default: ensemble-gemini3-opus
"""

OVERRIDE_CONFIG_YAML = """\
reviewers:
  single-opus:
    worker-model: opus
    worker-count: 1
    dispatch: tool-use
  single-sonnet:
    worker-model: sonnet
    worker-count: 1
    dispatch: tool-use
  single-haiku:
    worker-model: haiku
    worker-count: 1
    dispatch: tool-use

review-modules:
  discussion:
    default: single-opus
  plan:
    1: single-opus
    default: single-sonnet
  code:
    default: single-sonnet
"""

BULK_DISCUSSION_CONFIG_YAML = """\
reviewers:
  bulk-reviewer:
    worker-model: gemini-3-pro
    worker-count: 3
    dispatch: bulk
    handler-model: opus
    prompt-template: plugins/mill/doc/modules/code-review-bulk.md
    max-bundle-chars: 200000

review-modules:
  discussion:
    default: bulk-reviewer
  plan:
    default: bulk-reviewer
  code:
    default: bulk-reviewer
"""

TOOL_USE_MULTI_CONFIG_YAML = """\
reviewers:
  bad-reviewer:
    worker-model: opus
    worker-count: 2
    dispatch: tool-use

review-modules:
  code:
    default: bad-reviewer
  plan:
    default: bad-reviewer
  discussion:
    default: bad-reviewer
"""

BULK_NO_TEMPLATE_CONFIG_YAML = """\
reviewers:
  no-template:
    worker-model: gemini-3-pro
    worker-count: 3
    dispatch: bulk
    handler-model: opus

review-modules:
  code:
    default: no-template
  plan:
    default: no-template
  discussion:
    default: no-template
"""

COERCE_CONFIG_YAML = """\
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

int-field: 42
bool-true: true
bool-false: false
string-field: hello
"""


# ============================================================================
# TestYamlParser
# ============================================================================

class TestYamlParser(unittest.TestCase):
    """Tests for the _parse_yaml() hand-parser."""

    def setUp(self):
        from spawn_reviewer import _parse_yaml
        self.parse = _parse_yaml

    def test_minimal_config_parses(self):
        """Round-trips through the minimal config shape."""
        data = self.parse(MINIMAL_CONFIG_YAML)
        self.assertIn("reviewers", data)
        self.assertIn("review-modules", data)
        self.assertIn("single-opus", data["reviewers"])

    def test_nested_mapping(self):
        """Nested keys parse correctly."""
        data = self.parse(MINIMAL_CONFIG_YAML)
        recipe = data["reviewers"]["ensemble-gemini3-opus"]
        self.assertEqual(recipe["worker-model"], "gemini-3-pro")
        self.assertEqual(recipe["handler-model"], "opus")

    def test_integer_coercion(self):
        """worker-count: 3 lands as integer 3, not string '3'."""
        data = self.parse(MINIMAL_CONFIG_YAML)
        count = data["reviewers"]["ensemble-gemini3-opus"]["worker-count"]
        self.assertIsInstance(count, int)
        self.assertEqual(count, 3)

    def test_bool_coercion_true(self):
        data = self.parse(COERCE_CONFIG_YAML)
        self.assertIs(data["bool-true"], True)

    def test_bool_coercion_false(self):
        data = self.parse(COERCE_CONFIG_YAML)
        self.assertIs(data["bool-false"], False)

    def test_plain_int_scalar(self):
        data = self.parse(COERCE_CONFIG_YAML)
        self.assertEqual(data["int-field"], 42)
        self.assertIsInstance(data["int-field"], int)

    def test_string_scalar_unchanged(self):
        data = self.parse(COERCE_CONFIG_YAML)
        self.assertEqual(data["string-field"], "hello")

    def test_review_modules_round_keys(self):
        """Per-round integer keys in review-modules parse as string keys."""
        data = self.parse(OVERRIDE_CONFIG_YAML)
        plan_cfg = data["review-modules"]["plan"]
        # The YAML key "1:" should parse to string "1"
        self.assertIn("1", plan_cfg)
        self.assertEqual(plan_cfg["1"], "single-opus")

    def test_max_bundle_chars_is_int(self):
        data = self.parse(MINIMAL_CONFIG_YAML)
        val = data["reviewers"]["ensemble-gemini3-opus"]["max-bundle-chars"]
        self.assertIsInstance(val, int)
        self.assertEqual(val, 200000)


# ============================================================================
# TestResolveReviewer
# ============================================================================

class TestResolveReviewer(unittest.TestCase):
    """Tests for resolve_reviewer()."""

    def setUp(self):
        from spawn_reviewer import _parse_yaml, load_config_from_text, resolve_reviewer
        self._parse_yaml = _parse_yaml
        self._load = load_config_from_text
        self._resolve = resolve_reviewer

    def _cfg(self, yaml_text):
        return self._load(yaml_text)

    def test_code_review_round1_default(self):
        """Round 1 resolves to ensemble-gemini3-opus (the code default)."""
        config = self._cfg(MINIMAL_CONFIG_YAML)
        recipe = self._resolve(config, "code", 1)
        self.assertEqual(recipe.name, "ensemble-gemini3-opus")
        self.assertEqual(recipe.worker_model, "gemini-3-pro")
        self.assertEqual(recipe.worker_count, 3)
        self.assertEqual(recipe.dispatch, "bulk")
        self.assertEqual(recipe.handler_model, "opus")

    def test_plan_review_round1_override(self):
        """Round 1 plan-review resolves to single-opus per the explicit override."""
        config = self._cfg(OVERRIDE_CONFIG_YAML)
        recipe = self._resolve(config, "plan", 1)
        self.assertEqual(recipe.name, "single-opus")
        self.assertEqual(recipe.worker_model, "opus")

    def test_plan_review_round2_default(self):
        """Round 2 plan-review falls back to default (single-sonnet)."""
        config = self._cfg(OVERRIDE_CONFIG_YAML)
        recipe = self._resolve(config, "plan", 2)
        self.assertEqual(recipe.name, "single-sonnet")

    def test_round_far_past_explicit_keys_uses_default(self):
        """Round 7 with no '7' key falls back to default."""
        config = self._cfg(OVERRIDE_CONFIG_YAML)
        recipe = self._resolve(config, "plan", 7)
        self.assertEqual(recipe.name, "single-sonnet")

    def test_reviewer_name_override(self):
        """Explicit reviewer_name_override bypasses resolution."""
        config = self._cfg(OVERRIDE_CONFIG_YAML)
        recipe = self._resolve(config, "code", 1, reviewer_name_override="single-haiku")
        self.assertEqual(recipe.name, "single-haiku")
        self.assertEqual(recipe.worker_model, "haiku")

    def test_discussion_review_tool_use_ok(self):
        """Discussion-review with tool-use dispatch is allowed."""
        config = self._cfg(MINIMAL_CONFIG_YAML)
        recipe = self._resolve(config, "discussion", 1)
        self.assertEqual(recipe.name, "single-opus")
        self.assertEqual(recipe.dispatch, "tool-use")

    def test_fallback_field_present(self):
        config = self._cfg(MINIMAL_CONFIG_YAML)
        recipe = self._resolve(config, "code", 1)
        self.assertEqual(recipe.fallback, "sonnet-single-maxeffort")

    def test_prompt_template_present(self):
        config = self._cfg(MINIMAL_CONFIG_YAML)
        recipe = self._resolve(config, "code", 1)
        self.assertEqual(recipe.prompt_template, "plugins/mill/doc/modules/code-review-bulk.md")

    def test_no_prompt_template_for_tool_use(self):
        """tool-use recipes have prompt_template=None."""
        config = self._cfg(MINIMAL_CONFIG_YAML)
        recipe = self._resolve(config, "discussion", 1)
        self.assertIsNone(recipe.prompt_template)


# ============================================================================
# TestConfigErrors
# ============================================================================

class TestConfigErrors(unittest.TestCase):
    """Tests for ConfigError raises."""

    def setUp(self):
        from spawn_reviewer import _parse_yaml, load_config_from_text, resolve_reviewer, ConfigError
        self._load = load_config_from_text
        self._resolve = resolve_reviewer
        self.ConfigError = ConfigError

    def _cfg(self, yaml_text):
        return self._load(yaml_text)

    def test_missing_review_modules_raises(self):
        """Config without review-modules block raises ConfigError with mill-setup hint."""
        config = {"reviewers": {"x": {"worker-model": "sonnet", "worker-count": 1, "dispatch": "tool-use"}}}
        with self.assertRaises(self.ConfigError) as ctx:
            self._resolve(config, "code", 1)
        self.assertIn("review-modules", str(ctx.exception))
        self.assertIn("mill-setup", str(ctx.exception))

    def test_missing_reviewer_name_raises(self):
        """Reviewer name present in review-modules but absent in reviewers raises ConfigError."""
        config = {
            "reviewers": {},
            "review-modules": {"code": {"default": "nonexistent"}, "plan": {"default": "nonexistent"}, "discussion": {"default": "nonexistent"}},
        }
        with self.assertRaises(self.ConfigError) as ctx:
            self._resolve(config, "code", 1)
        self.assertIn("nonexistent", str(ctx.exception))

    def test_discussion_bulk_dispatch_raises(self):
        """discussion-review with bulk dispatch raises ConfigError."""
        config = self._cfg(BULK_DISCUSSION_CONFIG_YAML)
        with self.assertRaises(self.ConfigError) as ctx:
            self._resolve(config, "discussion", 1)
        self.assertIn("discussion", str(ctx.exception).lower())
        self.assertIn("bulk", str(ctx.exception).lower())

    def test_tool_use_multi_worker_raises(self):
        """tool-use with worker-count >= 2 raises ConfigError."""
        config = self._cfg(TOOL_USE_MULTI_CONFIG_YAML)
        with self.assertRaises(self.ConfigError) as ctx:
            self._resolve(config, "code", 1)
        self.assertIn("tool-use", str(ctx.exception))
        self.assertIn("worker-count", str(ctx.exception))

    def test_bulk_no_template_raises(self):
        """bulk dispatch without prompt-template raises ConfigError."""
        config = self._cfg(BULK_NO_TEMPLATE_CONFIG_YAML)
        with self.assertRaises(self.ConfigError) as ctx:
            self._resolve(config, "code", 1)
        self.assertIn("prompt-template", str(ctx.exception))

    def test_missing_default_raises(self):
        """review-modules.code without default raises ConfigError."""
        config = {
            "reviewers": {"x": {"worker-model": "sonnet", "worker-count": 1, "dispatch": "tool-use"}},
            "review-modules": {"code": {"1": "x"}, "plan": {"default": "x"}, "discussion": {"default": "x"}},
        }
        with self.assertRaises(self.ConfigError) as ctx:
            self._resolve(config, "code", 2)
        self.assertIn("default", str(ctx.exception))

    def test_bulk_fallback_raises(self):
        """Fallback recipe with dispatch='bulk' raises ConfigError — fallback must be tool-use."""
        config = {
            "reviewers": {
                "primary": {
                    "worker-model": "gemini-3-pro", "worker-count": 3, "dispatch": "bulk",
                    "handler-model": "sonnet", "prompt-template": "tmpl.md",
                    "fallback": "bad-fallback",
                },
                "bad-fallback": {
                    "worker-model": "gemini-3-pro", "worker-count": 3, "dispatch": "bulk",
                    "handler-model": "sonnet", "prompt-template": "tmpl.md",
                },
            },
            "review-modules": {
                "code": {"default": "primary"},
                "plan": {"default": "primary"},
                "discussion": {"default": "primary"},
            },
        }
        with self.assertRaises(self.ConfigError) as ctx:
            self._resolve(config, "code", 1)
        self.assertIn("bulk", str(ctx.exception))


# ============================================================================
# Step 4 tests: file-scope gathering
# (These tests exercise gather_file_scope and read_bundle_files.)
# ============================================================================

class TestGatherFileScope(unittest.TestCase):

    def setUp(self):
        from spawn_reviewer import gather_file_scope, read_bundle_files
        self.gather = gather_file_scope
        self.read_bundle = read_bundle_files

    def test_code_scope_calls_git_diff(self):
        """gather_file_scope for code runs git diff --name-only."""
        import unittest.mock as mock
        fake_output = "plugins/mill/scripts/spawn-agent.ps1\nplugins/mill/scripts/spawn-reviewer.py\n"
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.MagicMock(returncode=0, stdout=fake_output, stderr="")
            result = self.gather("code", ".", plan_start_hash="abc123")
        m.assert_called_once()
        args = m.call_args[0][0]
        self.assertIn("git", args[0])
        self.assertIn("diff", args)
        self.assertIn("--name-only", args)
        self.assertEqual(result, [
            "plugins/mill/scripts/spawn-agent.ps1",
            "plugins/mill/scripts/spawn-reviewer.py",
        ])

    def test_code_scope_requires_hash(self):
        """gather_file_scope for code without plan_start_hash raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.gather("code", ".")
        self.assertIn("plan_start_hash", str(ctx.exception))

    def test_plan_scope_parses_files_section(self):
        """gather_file_scope for plan parses ## Files section from plan.md."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# My Plan\n\n## Files\n\n- foo/bar.py\n* baz/qux.ts\n\n## Other\n\n- ignored.py\n")
            plan_path = f.name
        try:
            result = self.gather("plan", ".", plan_path=plan_path)
            self.assertEqual(result, ["foo/bar.py", "baz/qux.ts"])
        finally:
            os.unlink(plan_path)

    def test_plan_scope_mixed_bullets(self):
        """Both - and * bullet styles are accepted."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("## Files\n\n- a.py\n* b.py\n- c.py\n")
            plan_path = f.name
        try:
            result = self.gather("plan", ".", plan_path=plan_path)
            self.assertEqual(result, ["a.py", "b.py", "c.py"])
        finally:
            os.unlink(plan_path)

    def test_discussion_scope_raises(self):
        """gather_file_scope for discussion raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.gather("discussion", ".")
        self.assertIn("no deterministic file scope", str(ctx.exception))

    def test_read_bundle_files(self):
        """read_bundle_files returns dict of path -> contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.py")
            p2 = os.path.join(tmpdir, "b.py")
            with open(p1, 'w', encoding='utf-8') as f:
                f.write("hello")
            with open(p2, 'w', encoding='utf-8') as f:
                f.write("world")
            result = self.read_bundle(["a.py", "b.py"], tmpdir)
            self.assertEqual(result["a.py"], "hello")
            self.assertEqual(result["b.py"], "world")

    def test_read_bundle_missing_raises(self):
        """read_bundle_files raises FileNotFoundError for missing paths."""
        with self.assertRaises(FileNotFoundError) as ctx:
            self.read_bundle(["missing.py"], "/nonexistent")
        self.assertIn("missing.py", str(ctx.exception))


# ============================================================================
# Step 5 tests: bundle materialization
# ============================================================================

class TestBundleMaterialization(unittest.TestCase):

    def setUp(self):
        from spawn_reviewer import materialize_bulk_prompt, enforce_bundle_size, BundleTooLargeError
        self.materialize = materialize_bulk_prompt
        self.enforce = enforce_bundle_size
        self.BundleTooLargeError = BundleTooLargeError

    def test_token_substitution(self):
        """All tokens are substituted correctly."""
        template = "Round: <ROUND>\nDiff: <DIFF>\nPlan: <PLAN_CONTENT>\nConstraints: <CONSTRAINTS_CONTENT>\n<FILE_BUNDLE>"
        result = self.materialize(
            template, "code",
            file_contents={"a.py": "print('hi')"},
            diff_text="--- a\n+++ b\n",
            plan_content="# Plan",
            constraints_content="no globals",
            round_num=2,
        )
        self.assertIn("Round: 2", result)
        self.assertIn("Diff: --- a", result)
        self.assertIn("Plan: # Plan", result)
        self.assertIn("Constraints: no globals", result)

    def test_file_bundle_format(self):
        """FILE_BUNDLE has the correct separator format."""
        template = "<FILE_BUNDLE>"
        result = self.materialize(
            template, "code",
            file_contents={"foo.py": "x=1", "bar.py": "y=2"},
            diff_text="",
            plan_content="",
            constraints_content="",
            round_num=1,
        )
        self.assertIn("===== FILE: foo.py =====", result)
        self.assertIn("x=1", result)
        self.assertIn("===== END FILE: foo.py =====", result)
        self.assertIn("===== FILE: bar.py =====", result)
        self.assertIn("y=2", result)

    def test_empty_file_bundle(self):
        """Empty file_contents produces empty FILE_BUNDLE substitution (no error)."""
        template = "before<FILE_BUNDLE>after"
        result = self.materialize(
            template, "code",
            file_contents={},
            diff_text="",
            plan_content="",
            constraints_content="",
            round_num=1,
        )
        self.assertEqual(result, "beforeafter")

    def test_unknown_tokens_pass_through(self):
        """Unknown tokens are left as-is, not an error."""
        template = "<FILE_BUNDLE><UNKNOWN_TOKEN>"
        result = self.materialize(
            template, "code",
            file_contents={},
            diff_text="",
            plan_content="",
            constraints_content="",
            round_num=1,
        )
        self.assertIn("<UNKNOWN_TOKEN>", result)

    def test_constraints_absent_placeholder(self):
        """When constraints_content is the no-CONSTRAINTS.md sentinel, it substitutes."""
        template = "<CONSTRAINTS_CONTENT>"
        result = self.materialize(
            template, "code",
            file_contents={},
            diff_text="",
            plan_content="",
            constraints_content="(no CONSTRAINTS.md)",
            round_num=1,
        )
        self.assertIn("(no CONSTRAINTS.md)", result)

    def test_enforce_bundle_size_ok(self):
        """enforce_bundle_size passes when under limit."""
        self.enforce("small text", 1000)

    def test_enforce_bundle_size_raises(self):
        """enforce_bundle_size raises BundleTooLargeError when over limit."""
        with self.assertRaises(self.BundleTooLargeError) as ctx:
            self.enforce("a" * 100, 50)
        self.assertIn("100", str(ctx.exception))
        self.assertIn("50", str(ctx.exception))

    def test_enforce_none_max_skips(self):
        """None max_bundle_chars skips the check."""
        self.enforce("a" * 100000, None)


# ============================================================================
# Step 6 tests: worker dispatch
# ============================================================================

class TestWorkerDispatch(unittest.TestCase):

    def setUp(self):
        from spawn_reviewer import (
            dispatch_workers, ReviewerRecipe, WorkerResults, WorkerResult, WorkerFailure
        )
        self.dispatch = dispatch_workers
        self.ReviewerRecipe = ReviewerRecipe
        self.WorkerResults = WorkerResults
        self.WorkerResult = WorkerResult
        self.WorkerFailure = WorkerFailure

    def _make_recipe(self, worker_model='sonnet', worker_count=1, dispatch='tool-use',
                     handler_model=None, max_bundle_chars=None, fallback=None,
                     prompt_template=None):
        return self.ReviewerRecipe(
            name='test-recipe',
            worker_model=worker_model,
            worker_count=worker_count,
            dispatch=dispatch,
            handler_model=handler_model,
            max_bundle_chars=max_bundle_chars,
            fallback=fallback,
            prompt_template=prompt_template,
        )

    def test_tool_use_single_worker_happy(self):
        """n=1 tool-use: single subprocess call, returns 1 success."""
        import unittest.mock as mock
        import json

        review_path = "/tmp/review.md"
        stdout_json = json.dumps({"verdict": "APPROVE", "review_file": review_path})

        recipe = self._make_recipe(worker_count=1, dispatch='tool-use')
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.MagicMock(returncode=0, stdout=stdout_json, stderr="")
            with tempfile.TemporaryDirectory() as tmpdir:
                result = self.dispatch(
                    recipe=recipe,
                    prompt_file_path="/fake/prompt.md",
                    materialized_prompt=None,
                    work_dir=tmpdir,
                    round_num=1,
                    reviews_dir_base=tmpdir,
                )
        self.assertEqual(len(result.successes), 1)
        self.assertEqual(len(result.failures), 0)
        self.assertIsNone(result.fatal)
        self.assertFalse(result.bot_gated)

    def test_bulk_n3_all_success(self):
        """n=3 bulk ensemble: 3 workers all succeed → 3 successes, 0 failures, no fatal."""
        import json
        import unittest.mock as mock

        recipe = self._make_recipe(
            worker_model='gemini-3-pro', worker_count=3, dispatch='bulk',
            handler_model='opus', prompt_template='tmpl.md',
        )

        def make_proc(review_file_path):
            p = mock.MagicMock()
            line = json.dumps({"verdict": "APPROVE", "review_file": review_file_path})
            p.communicate.return_value = (line.encode(), b"")
            p.returncode = 0
            return p

        with mock.patch("subprocess.Popen") as m:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Pre-create review files so WorkerResult paths are valid
                review_paths = [os.path.join(tmpdir, f'r{i}.md') for i in range(1, 4)]
                for rp in review_paths:
                    with open(rp, 'w') as f:
                        f.write("stub")
                procs = [make_proc(rp) for rp in review_paths]
                m.side_effect = procs
                result = self.dispatch(
                    recipe=recipe,
                    prompt_file_path=None,
                    materialized_prompt="fake prompt\nVERDICT: APPROVE",
                    work_dir=tmpdir,
                    round_num=1,
                    reviews_dir_base=tmpdir,
                )
        self.assertEqual(m.call_count, 3)
        self.assertEqual(len(result.successes), 3)
        self.assertEqual(len(result.failures), 0)
        self.assertIsNone(result.fatal)

    def test_rate_limit_failure_classification(self):
        """Worker exit code 10 → WorkerFailure(kind='rate_limit')."""
        import unittest.mock as mock

        recipe = self._make_recipe(
            worker_model='gemini-3-pro', worker_count=3, dispatch='bulk',
            handler_model='opus', prompt_template='tmpl.md',
        )

        def make_proc(exit_code, stderr_text):
            p = mock.MagicMock()
            p.communicate.return_value = (b"", stderr_text.encode())
            p.returncode = exit_code
            return p

        with mock.patch("subprocess.Popen") as m:
            m.side_effect = [
                make_proc(0, ""),
                make_proc(10, "[spawn-agent] gemini 429 rate limit"),
                make_proc(10, "[spawn-agent] gemini 429 rate limit"),
            ]
            with tempfile.TemporaryDirectory() as tmpdir:
                result = self.dispatch(
                    recipe=recipe,
                    prompt_file_path=None,
                    materialized_prompt="fake prompt\nVERDICT: APPROVE",
                    work_dir=tmpdir,
                    round_num=1,
                    reviews_dir_base=tmpdir,
                )
        rate_limit_failures = [f for f in result.failures if f.kind == 'rate_limit']
        self.assertEqual(len(rate_limit_failures), 2)

    def test_bot_gate_sets_flag(self):
        """Worker exit code 11 → bot_gated=True in WorkerResults."""
        import unittest.mock as mock

        recipe = self._make_recipe(
            worker_model='gemini-3-pro', worker_count=3, dispatch='bulk',
            handler_model='opus', prompt_template='tmpl.md',
        )

        def make_proc(exit_code):
            p = mock.MagicMock()
            p.communicate.return_value = (b"", b"")
            p.returncode = exit_code
            return p

        with mock.patch("subprocess.Popen") as m:
            m.side_effect = [
                make_proc(0),
                make_proc(0),
                make_proc(11),  # bot-gate
            ]
            with tempfile.TemporaryDirectory() as tmpdir:
                result = self.dispatch(
                    recipe=recipe,
                    prompt_file_path=None,
                    materialized_prompt="fake\nVERDICT: APPROVE",
                    work_dir=tmpdir,
                    round_num=1,
                    reviews_dir_base=tmpdir,
                )
        self.assertTrue(result.bot_gated)
        bot_failures = [f for f in result.failures if f.kind == 'bot_gate']
        self.assertEqual(len(bot_failures), 1)

    def test_degraded_fatal_on_two_failures(self):
        """When successes < 2 for a 3-worker ensemble → fatal='degraded-fatal'."""
        import unittest.mock as mock

        recipe = self._make_recipe(
            worker_model='gemini-3-pro', worker_count=3, dispatch='bulk',
            handler_model='opus', prompt_template='tmpl.md',
        )

        def make_proc(exit_code):
            p = mock.MagicMock()
            p.communicate.return_value = (b"", b"")
            p.returncode = exit_code
            return p

        with mock.patch("subprocess.Popen") as m:
            m.side_effect = [
                make_proc(10),
                make_proc(10),
                make_proc(0),
            ]
            with tempfile.TemporaryDirectory() as tmpdir:
                result = self.dispatch(
                    recipe=recipe,
                    prompt_file_path=None,
                    materialized_prompt="fake\nVERDICT: APPROVE",
                    work_dir=tmpdir,
                    round_num=1,
                    reviews_dir_base=tmpdir,
                )
        self.assertEqual(result.fatal, "degraded-fatal")

    def test_bulk_malformed_missing_verdict_field(self):
        """Worker stdout is parseable JSON but missing 'verdict' field → malformed failure."""
        import unittest.mock as mock

        recipe = self._make_recipe(
            worker_model='gemini-3-pro', worker_count=3, dispatch='bulk',
            handler_model='opus', prompt_template='tmpl.md',
        )

        def make_proc(stdout_text, exit_code=0):
            p = mock.MagicMock()
            p.communicate.return_value = (stdout_text.encode(), b"")
            p.returncode = exit_code
            return p

        with mock.patch("subprocess.Popen") as m:
            # Worker 1: valid JSON but missing 'verdict' key
            # Workers 2, 3: exit 10 (rate_limit) to ensure degraded-fatal doesn't obscure
            m.side_effect = [
                make_proc('{"review_file": "/tmp/r.md"}'),  # parseable, no verdict
                make_proc('', exit_code=10),
                make_proc('', exit_code=10),
            ]
            with tempfile.TemporaryDirectory() as tmpdir:
                result = self.dispatch(
                    recipe=recipe,
                    prompt_file_path=None,
                    materialized_prompt="fake\nVERDICT: APPROVE",
                    work_dir=tmpdir,
                    round_num=1,
                    reviews_dir_base=tmpdir,
                )
        malformed = [f for f in result.failures if f.kind == 'malformed']
        self.assertEqual(len(malformed), 1)
        self.assertEqual(malformed[0].worker_id, 1)

    def test_bulk_worker_timeout(self):
        """Worker hangs past communicate timeout → WorkerFailure(kind='timeout')."""
        import subprocess
        import unittest.mock as mock

        recipe = self._make_recipe(
            worker_model='gemini-3-pro', worker_count=3, dispatch='bulk',
            handler_model='opus', prompt_template='tmpl.md',
        )

        def make_timed_out_proc():
            p = mock.MagicMock()
            p.communicate.side_effect = subprocess.TimeoutExpired(cmd='ps', timeout=600)
            p.returncode = -1
            return p

        def make_proc(exit_code=10):
            p = mock.MagicMock()
            p.communicate.return_value = (b"", b"")
            p.returncode = exit_code
            return p

        with mock.patch("subprocess.Popen") as m:
            m.side_effect = [
                make_timed_out_proc(),  # worker 1 times out
                make_proc(10),          # worker 2 rate-limited
                make_proc(10),          # worker 3 rate-limited
            ]
            with tempfile.TemporaryDirectory() as tmpdir:
                result = self.dispatch(
                    recipe=recipe,
                    prompt_file_path=None,
                    materialized_prompt="fake\nVERDICT: APPROVE",
                    work_dir=tmpdir,
                    round_num=1,
                    reviews_dir_base=tmpdir,
                )
        timeout_failures = [f for f in result.failures if f.kind == 'timeout']
        self.assertEqual(len(timeout_failures), 1)
        self.assertEqual(timeout_failures[0].worker_id, 1)

    def test_tool_use_missing_prompt_file_raises(self):
        """dispatch_workers for tool-use without prompt_file_path raises ValueError."""
        recipe = self._make_recipe(worker_count=1, dispatch='tool-use')
        with self.assertRaises(ValueError) as ctx:
            self.dispatch(recipe, None, None, ".", 1, ".")
        self.assertIn("prompt_file_path", str(ctx.exception))

    def test_bulk_missing_materialized_prompt_raises(self):
        """dispatch_workers for bulk without materialized_prompt raises ValueError."""
        recipe = self._make_recipe(
            worker_count=3, dispatch='bulk', handler_model='opus', prompt_template='t.md',
        )
        with self.assertRaises(ValueError) as ctx:
            self.dispatch(recipe, None, None, ".", 1, ".")
        self.assertIn("materialized_prompt", str(ctx.exception))


# ============================================================================
# Step 7 tests: handler spawn and fallback
# ============================================================================

class TestHandlerAndFallback(unittest.TestCase):

    def setUp(self):
        from spawn_reviewer import ReviewerRecipe, WorkerResults, WorkerResult, WorkerFailure
        self.ReviewerRecipe = ReviewerRecipe
        self.WorkerResults = WorkerResults
        self.WorkerResult = WorkerResult
        self.WorkerFailure = WorkerFailure

    def _make_recipe(self, name='test', worker_model='sonnet', worker_count=1,
                     dispatch='tool-use', handler_model=None, fallback=None,
                     prompt_template=None, max_bundle_chars=None):
        return self.ReviewerRecipe(
            name=name, worker_model=worker_model, worker_count=worker_count,
            dispatch=dispatch, handler_model=handler_model, fallback=fallback,
            prompt_template=prompt_template, max_bundle_chars=max_bundle_chars,
        )

    def _make_worker_result(self, verdict="APPROVE", review_file="/tmp/r.md"):
        return self.WorkerResult(
            worker_id=1, verdict=verdict, review_file=review_file,
        )

    def _make_worker_results(self, successes=None, failures=None,
                              bot_gated=False, fatal=None, invocation_dir="/tmp"):
        return self.WorkerResults(
            successes=successes or [],
            failures=failures or [],
            bot_gated=bot_gated,
            fatal=fatal,
            invocation_dir=invocation_dir,
        )

    def test_spawn_handler_happy(self):
        """spawn_handler returns the handler's JSON verdict."""
        import unittest.mock as mock
        import json

        from spawn_reviewer import spawn_handler

        handler_report = "/tmp/ts-code-review-r1.md"
        handler_json = json.dumps({"verdict": "APPROVE", "review_file": handler_report})

        recipe = self._make_recipe(handler_model="opus", worker_count=3, dispatch="bulk",
                                   prompt_template="tmpl.md")
        worker_results = self._make_worker_results(
            successes=[self._make_worker_result()],
            invocation_dir="/tmp/ts",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake worker report file
            r1 = os.path.join(tmpdir, "r1.md")
            with open(r1, 'w') as f:
                f.write("## Summary\nok\n")

            # Create the skill file the handler reads
            skill_dir = os.path.join(tmpdir, "plugins", "mill", "skills", "review-handler")
            os.makedirs(skill_dir, exist_ok=True)
            skill_path = os.path.join(skill_dir, "SKILL.md")
            with open(skill_path, 'w') as f:
                f.write("---\nname: review-handler\n---\n# Handler prompt\n<N> <PHASE> <WORKER_REPORT_PATHS> <COMBINED_REPORT_PATH> <DEGRADATION_NOTE>\n")

            invocation_dir = tmpdir

            with mock.patch("subprocess.run") as m:
                m.return_value = mock.MagicMock(returncode=0, stdout=handler_json, stderr="")
                result = spawn_handler(
                    recipe=recipe,
                    worker_results=worker_results,
                    phase="code",
                    round_num=1,
                    reviews_dir=invocation_dir,
                    task_reviews_dir=tmpdir,
                    work_dir=tmpdir,
                )
        self.assertEqual(result.verdict, "APPROVE")
        self.assertEqual(result.review_file, handler_report)

    def test_no_handler_for_solo_recipe(self):
        """n=1 tool-use recipe with no handler_model: single worker JSON is emitted directly."""
        from spawn_reviewer import spawn_handler

        recipe = self._make_recipe(handler_model=None, worker_count=1, dispatch="tool-use")
        worker_results = self._make_worker_results(
            successes=[self._make_worker_result(verdict="APPROVE", review_file="/tmp/solo.md")],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = spawn_handler(
                recipe=recipe,
                worker_results=worker_results,
                phase="code",
                round_num=1,
                reviews_dir=tmpdir,
                task_reviews_dir=tmpdir,
                work_dir=tmpdir,
            )
        self.assertEqual(result.verdict, "APPROVE")
        self.assertEqual(result.review_file, "/tmp/solo.md")


class TestBotGate(unittest.TestCase):
    """Bot-gate marker writing, detection, and fallback dispatch (Plan Step 7)."""

    def test_bot_gate_marker_written_to_expected_path(self):
        """_write_bot_gate_marker creates a flag file named bot-gated-<recipe>.flag."""
        from spawn_reviewer import _write_bot_gate_marker, _bot_gate_marker_path

        with tempfile.TemporaryDirectory() as tmpdir:
            _write_bot_gate_marker(tmpdir, "ensemble-gemini3-opus")
            expected = os.path.join(tmpdir, "bot-gated-ensemble-gemini3-opus.flag")
            self.assertTrue(os.path.exists(expected))
            self.assertEqual(_bot_gate_marker_path(tmpdir, "ensemble-gemini3-opus"), expected)
            with open(expected, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("bot-gated at", content)

    def test_bot_gate_marker_detection_is_per_recipe(self):
        """_check_bot_gate_marker returns True only for recipes that have been marked."""
        from spawn_reviewer import _write_bot_gate_marker, _check_bot_gate_marker

        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertFalse(_check_bot_gate_marker(tmpdir, "ensemble-gemini3-opus"))
            _write_bot_gate_marker(tmpdir, "ensemble-gemini3-opus")
            self.assertTrue(_check_bot_gate_marker(tmpdir, "ensemble-gemini3-opus"))
            self.assertFalse(_check_bot_gate_marker(tmpdir, "some-other-recipe"))

    def test_bot_gate_no_fallback_exits_nonzero(self):
        """main() exits non-zero when bot-gated and recipe has no fallback."""
        import unittest.mock as mock

        from spawn_reviewer import ReviewerRecipe, WorkerResults
        import spawn_reviewer

        recipe = ReviewerRecipe(
            name="ensemble-no-fallback",
            worker_model="gemini-3-pro", worker_count=3, dispatch="bulk",
            handler_model="opus", max_bundle_chars=200000,
            fallback=None, prompt_template="plugins/mill/doc/modules/code-review-bulk.md",
        )
        bot_gated_results = WorkerResults(
            successes=[], failures=[], bot_gated=True, fatal=None,
            invocation_dir="/tmp/x",
        )

        with mock.patch.object(spawn_reviewer, "resolve_reviewer", return_value=recipe), \
             mock.patch.object(spawn_reviewer, "load_config", return_value={}), \
             mock.patch.object(spawn_reviewer, "dispatch_workers", return_value=bot_gated_results), \
             mock.patch.object(spawn_reviewer, "_write_bot_gate_marker") as marker_write, \
             mock.patch("sys.argv", [
                "spawn-reviewer.py",
                "--reviewer-name", "ensemble-no-fallback",
                "--prompt-file", "/tmp/p.md",
                "--phase", "code",
                "--round", "1",
                "--plan-start-hash", "abc123",
             ]):
            with self.assertRaises(SystemExit) as ctx:
                spawn_reviewer.main()
        self.assertNotEqual(ctx.exception.code, 0)
        marker_write.assert_called_once()

    def test_bot_gate_with_fallback_dispatches_fallback_recipe(self):
        """main() re-dispatches against the configured fallback recipe on bot-gate."""
        import unittest.mock as mock

        from spawn_reviewer import (
            ReviewerRecipe, WorkerResults, WorkerResult, HandlerResult,
        )
        import spawn_reviewer

        primary = ReviewerRecipe(
            name="ensemble-gemini3-opus",
            worker_model="gemini-3-pro", worker_count=3, dispatch="bulk",
            handler_model="opus", max_bundle_chars=200000,
            fallback="sonnet-single-maxeffort",
            prompt_template="plugins/mill/doc/modules/code-review-bulk.md",
        )
        fallback = ReviewerRecipe(
            name="sonnet-single-maxeffort",
            worker_model="sonnet", worker_count=1, dispatch="tool-use",
            handler_model=None, max_bundle_chars=None,
            fallback=None, prompt_template=None,
        )

        bot_gated_results = WorkerResults(
            successes=[], failures=[], bot_gated=True, fatal=None,
            invocation_dir="/tmp/x",
        )
        ok_results = WorkerResults(
            successes=[WorkerResult(worker_id=1, verdict="APPROVE", review_file="/tmp/r.md")],
            failures=[], bot_gated=False, fatal=None,
            invocation_dir="/tmp/y",
        )
        handler_result = HandlerResult(verdict="APPROVE", review_file="/tmp/r.md")

        resolve_calls = [primary, fallback]
        def fake_resolve(*args, **kwargs):
            return resolve_calls.pop(0)

        with mock.patch.object(spawn_reviewer, "resolve_reviewer", side_effect=fake_resolve), \
             mock.patch.object(spawn_reviewer, "load_config", return_value={}), \
             mock.patch.object(spawn_reviewer, "dispatch_workers",
                               side_effect=[bot_gated_results, ok_results]) as dispatch_mock, \
             mock.patch.object(spawn_reviewer, "spawn_handler", return_value=handler_result), \
             mock.patch.object(spawn_reviewer, "_write_bot_gate_marker"), \
             mock.patch("sys.argv", [
                "spawn-reviewer.py",
                "--reviewer-name", "ensemble-gemini3-opus",
                "--prompt-file", "/tmp/p.md",
                "--phase", "code",
                "--round", "1",
                "--plan-start-hash", "abc123",
             ]):
            spawn_reviewer.main()
        self.assertEqual(dispatch_mock.call_count, 2)
        second_call_recipe = dispatch_mock.call_args_list[1].kwargs["recipe"]
        self.assertEqual(second_call_recipe.name, "sonnet-single-maxeffort")


if __name__ == "__main__":
    unittest.main()
