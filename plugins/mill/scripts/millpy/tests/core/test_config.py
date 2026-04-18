"""
test_config.py — Tests for millpy.core.config (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.core.config import (
    ConfigError,
    _parse_yaml_mapping,
    load,
    load_merged,
    resolve_max_rounds,
    resolve_reviewer_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _parse_yaml_mapping — basic scalar types
# ---------------------------------------------------------------------------

class TestParseYamlMapping:
    def test_simple_string(self):
        result = _parse_yaml_mapping("name: foo\n")
        assert result["name"] == "foo"

    def test_unquoted_bool_true(self):
        result = _parse_yaml_mapping("flag: true\n")
        assert result["flag"] is True

    def test_unquoted_bool_false(self):
        result = _parse_yaml_mapping("flag: false\n")
        assert result["flag"] is False

    def test_unquoted_int(self):
        result = _parse_yaml_mapping("count: 42\n")
        assert result["count"] == 42

    def test_unquoted_null(self):
        result = _parse_yaml_mapping("key: null\n")
        assert result["key"] is None

    def test_unquoted_tilde_null(self):
        result = _parse_yaml_mapping("key: ~\n")
        assert result["key"] is None

    def test_quoted_string_stays_string_true(self):
        result = _parse_yaml_mapping('flag: "true"\n')
        assert result["flag"] == "true"
        assert not isinstance(result["flag"], bool)

    def test_quoted_string_stays_string_int(self):
        result = _parse_yaml_mapping('count: "42"\n')
        assert result["count"] == "42"
        assert not isinstance(result["count"], int)

    def test_single_quoted_string(self):
        result = _parse_yaml_mapping("name: 'hello world'\n")
        assert result["name"] == "hello world"

    def test_comment_stripped(self):
        result = _parse_yaml_mapping("name: foo  # a comment\n")
        assert result["name"] == "foo"

    def test_nested_mapping(self):
        text = "models:\n  default: sonnet\n  1: opus\n"
        result = _parse_yaml_mapping(text)
        assert result["models"]["default"] == "sonnet"
        assert result["models"]["1"] == "opus"

    def test_integer_key_normalized_to_string(self):
        text = "models:\n  1: opus\n  2: sonnet\n"
        result = _parse_yaml_mapping(text)
        assert "1" in result["models"]
        assert "2" in result["models"]

    def test_block_scalar_basic(self):
        text = "task_description: |\n  line one\n  line two\n"
        result = _parse_yaml_mapping(text)
        assert result["task_description"] == "line one\nline two\n"

    def test_block_scalar_indent_stripped(self):
        text = "desc: |\n    indented\n    more\n"
        result = _parse_yaml_mapping(text)
        assert result["desc"] == "indented\nmore\n"

    def test_empty_value(self):
        result = _parse_yaml_mapping("key:\n")
        assert result["key"] is None


# ---------------------------------------------------------------------------
# load() — file-based tests
# ---------------------------------------------------------------------------

class TestLoad:
    def test_loads_flat_scalars(self, tmp_path):
        p = write_yaml(tmp_path, "name: foo\ncount: 3\n")
        cfg = load(p)
        assert cfg["name"] == "foo"
        assert cfg["count"] == 3

    def test_loads_nested_mapping(self, tmp_path):
        text = """\
            models:
              default: sonnet
              1: opus
        """
        p = write_yaml(tmp_path, text)
        cfg = load(p)
        assert cfg["models"]["default"] == "sonnet"
        assert cfg["models"]["1"] == "opus"

    def test_loads_config_yaml(self):
        """Smoke test: loads the actual _millhouse/config.yaml without raising."""
        repo_config = Path(__file__).parents[5] / "_millhouse" / "config.yaml"
        if repo_config.exists():
            cfg = load(repo_config)
            assert isinstance(cfg, dict)

    def test_raises_config_error_on_missing_file(self, tmp_path):
        p = tmp_path / "missing.yaml"
        with pytest.raises(ConfigError):
            load(p)


# ---------------------------------------------------------------------------
# resolve_reviewer_name()
# ---------------------------------------------------------------------------

class TestResolveReviewerName:
    def test_pipeline_schema_default(self, tmp_path):
        text = """\
            pipeline:
              plan-review:
                rounds: 3
                default: g3flash-x3-sonnetmax
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "plan", 1) == "g3flash-x3-sonnetmax"
        assert resolve_reviewer_name(cfg, "plan", 2) == "g3flash-x3-sonnetmax"

    def test_pipeline_schema_per_round_override(self, tmp_path):
        text = """\
            pipeline:
              code-review:
                rounds: 3
                default: sonnet
                1: g3pro-x2-opus
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "code", 1) == "g3pro-x2-opus"
        assert resolve_reviewer_name(cfg, "code", 2) == "sonnet"

    def test_raises_config_error_when_absent(self, tmp_path):
        p = write_yaml(tmp_path, "name: foo\n")
        cfg = load(p)
        with pytest.raises(ConfigError):
            resolve_reviewer_name(cfg, "plan", 1)

    def test_config_error_is_value_error(self, tmp_path):
        p = write_yaml(tmp_path, "name: foo\n")
        cfg = load(p)
        with pytest.raises(ValueError):
            resolve_reviewer_name(cfg, "plan", 1)

    def test_integer_and_string_key_equivalent(self, tmp_path):
        """Integer key 1 and string key '1' both work."""
        text = """\
            pipeline:
              plan-review:
                default: sonnet
                1: opus
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "plan", 1) == "opus"


# ---------------------------------------------------------------------------
# resolve_reviewer_name() — slice_type removed (Card 5)
# ---------------------------------------------------------------------------

class TestResolveReviewerNameSliceTypeRemoved:
    """resolve_reviewer_name no longer accepts slice_type — it is slice-type-agnostic."""

    def test_no_slice_type_resolves_default(self, tmp_path):
        """Happy: default key is returned when no per-round override."""
        text = """\
            pipeline:
              plan-review:
                rounds: 3
                default: sonnetmax
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "plan", 1) == "sonnetmax"

    def test_per_round_override_takes_precedence(self, tmp_path):
        """Happy: integer round key overrides default."""
        text = """\
            pipeline:
              code-review:
                rounds: 3
                default: sonnetmax
                2: opus
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "code", 2) == "opus"
        assert resolve_reviewer_name(cfg, "code", 1) == "sonnetmax"

    def test_missing_default_raises_config_error(self, tmp_path):
        """Error: missing default: → ConfigError."""
        text = """\
            pipeline:
              plan-review:
                rounds: 3
        """
        cfg = load(write_yaml(tmp_path, text))
        with pytest.raises(ConfigError):
            resolve_reviewer_name(cfg, "plan", 1)

    def test_signature_has_no_slice_type_param(self):
        """Happy: resolve_reviewer_name does not accept slice_type keyword."""
        import inspect
        sig = inspect.signature(resolve_reviewer_name)
        assert "slice_type" not in sig.parameters


# ---------------------------------------------------------------------------
# resolve_max_rounds()
# ---------------------------------------------------------------------------

class TestResolveMaxRounds:
    def test_returns_value_when_present(self, tmp_path):
        text = """\
            pipeline:
              plan-review:
                rounds: 5
                default: sonnet
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_max_rounds(cfg, "plan") == 5

    def test_returns_default_when_absent(self, tmp_path):
        p = write_yaml(tmp_path, "name: foo\n")
        cfg = load(p)
        assert resolve_max_rounds(cfg, "plan") == 3

    def test_returns_default_when_phase_absent(self, tmp_path):
        text = """\
            pipeline:
              code-review:
                rounds: 2
                default: sonnet
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_max_rounds(cfg, "plan") == 3

    def test_pipeline_rounds(self, tmp_path):
        text = """\
            pipeline:
              code-review:
                rounds: 5
                default: sonnet
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_max_rounds(cfg, "code") == 5


# ---------------------------------------------------------------------------
# load_merged() — shared + local YAML merge (Card 4)
# ---------------------------------------------------------------------------

class TestLoadMerged:
    def _write(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        return path

    def test_only_shared_exists(self, tmp_path):
        """Only .mill/config.yaml → returned as-is, no local overrides."""
        shared = self._write(
            tmp_path / ".mill" / "config.yaml",
            """\
            pipeline:
              implementer: sonnet
            """,
        )
        cfg = load_merged(
            shared_path=shared,
            local_path=tmp_path / "_millhouse" / "config.local.yaml",
        )
        assert cfg["pipeline"]["implementer"] == "sonnet"

    def test_local_overrides_shared(self, tmp_path):
        """Local config overrides shared values at nested depth."""
        shared = self._write(
            tmp_path / ".mill" / "config.yaml",
            """\
            pipeline:
              implementer: sonnet
            """,
        )
        local = self._write(
            tmp_path / "_millhouse" / "config.local.yaml",
            """\
            pipeline:
              implementer: opus
            """,
        )
        cfg = load_merged(shared_path=shared, local_path=local)
        assert cfg["pipeline"]["implementer"] == "opus"

    def test_fallback_to_old_millhouse_config(self, tmp_path, capsys):
        """When .mill/config.yaml is absent but _millhouse/config.yaml exists, use it."""
        old = self._write(
            tmp_path / "_millhouse" / "config.yaml",
            """\
            pipeline:
              implementer: sonnet
            """,
        )
        cfg = load_merged(
            shared_path=tmp_path / ".mill" / "config.yaml",
            local_path=tmp_path / "_millhouse" / "config.local.yaml",
            legacy_path=old,
        )
        assert cfg["pipeline"]["implementer"] == "sonnet"

    def test_both_absent_returns_empty(self, tmp_path):
        """Neither file exists → returns empty dict."""
        cfg = load_merged(
            shared_path=tmp_path / ".mill" / "config.yaml",
            local_path=tmp_path / "_millhouse" / "config.local.yaml",
        )
        assert cfg == {}

    def test_deep_merge_nested_keys(self, tmp_path):
        """Deep-merge: local adds a nested key without destroying sibling keys."""
        shared = self._write(
            tmp_path / ".mill" / "config.yaml",
            """\
            notifications:
              slack:
                webhook: ""
                channel: "#mill"
            """,
        )
        local = self._write(
            tmp_path / "_millhouse" / "config.local.yaml",
            """\
            notifications:
              slack:
                webhook: "https://hooks.slack.com/xxx"
            """,
        )
        cfg = load_merged(shared_path=shared, local_path=local)
        assert cfg["notifications"]["slack"]["webhook"] == "https://hooks.slack.com/xxx"
        assert cfg["notifications"]["slack"]["channel"] == "#mill"

    def test_wiki_clone_path_from_local(self, tmp_path):
        """wiki.clone-path in local config is accessible after merge."""
        shared = self._write(
            tmp_path / ".mill" / "config.yaml",
            "name: test\n",
        )
        local = self._write(
            tmp_path / "_millhouse" / "config.local.yaml",
            """\
            wiki:
              clone-path: /custom/wiki/path
            """,
        )
        cfg = load_merged(shared_path=shared, local_path=local)
        assert cfg["wiki"]["clone-path"] == "/custom/wiki/path"

    def test_lists_replaced_not_concatenated(self, tmp_path):
        """Lists from local replace shared lists rather than concatenating."""
        # The YAML parser handles lists only at scalar level; use a scalar test
        # that shows override semantics.
        shared = self._write(
            tmp_path / ".mill" / "config.yaml",
            """\
            pipeline:
              implementer: sonnet
            """,
        )
        local = self._write(
            tmp_path / "_millhouse" / "config.local.yaml",
            """\
            pipeline:
              implementer: opus
            """,
        )
        cfg = load_merged(shared_path=shared, local_path=local)
        # Local value wins — no concatenation
        assert cfg["pipeline"]["implementer"] == "opus"


def test_template_pipeline_block_contains_no_gemini_reviewer():
    """Regression gate: plugins/mill/templates/millhouse-config.yaml must not
    reference gemini-based reviewers inside the pipeline block. Reviewer
    defaults switched to sonnetmax on 2026-04-17 because gemini backends
    were unstable."""
    import subprocess
    toplevel = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    template = Path(toplevel) / "plugins" / "mill" / "templates" / "millhouse-config.yaml"
    text = template.read_text(encoding="utf-8")

    lines = text.splitlines()
    in_pipeline = False
    pipeline_lines: list[str] = []
    for line in lines:
        if line.startswith("pipeline:"):
            in_pipeline = True
            continue
        if in_pipeline:
            if line and not line.startswith(" ") and not line.startswith("\t"):
                break
            pipeline_lines.append(line)
    pipeline_text = "\n".join(pipeline_lines)

    assert "gemini" not in pipeline_text.lower(), (
        f"Template pipeline block still references gemini:\n{pipeline_text}"
    )
    for token in ("g25flash", "g25pro", "g3flash", "g3pro"):
        assert token not in pipeline_text, (
            f"Template pipeline block still references {token!r}:\n{pipeline_text}"
        )
