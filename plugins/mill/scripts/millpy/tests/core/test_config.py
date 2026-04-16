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
# resolve_reviewer_name() — slice_type parameter
# ---------------------------------------------------------------------------

class TestResolveReviewerNameSliceType:
    def test_slice_type_holistic_resolves_from_holistic_key(self, tmp_path):
        text = """\
            pipeline:
              plan-review:
                rounds: 3
                default: g3flash-x3-sonnetmax
                holistic: sonnetmax
                per-card: g3flash
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "plan", 1, slice_type="holistic") == "sonnetmax"

    def test_slice_type_per_card_resolves_from_per_card_key(self, tmp_path):
        text = """\
            pipeline:
              plan-review:
                rounds: 3
                default: g3flash-x3-sonnetmax
                holistic: sonnetmax
                per-card: g3flash
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "plan", 1, slice_type="per-card") == "g3flash"

    def test_no_slice_type_returns_default_backward_compat(self, tmp_path):
        text = """\
            pipeline:
              plan-review:
                rounds: 3
                default: g3flash-x3-sonnetmax
                holistic: sonnetmax
                per-card: g3flash
        """
        cfg = load(write_yaml(tmp_path, text))
        assert resolve_reviewer_name(cfg, "plan", 1) == "g3flash-x3-sonnetmax"

    def test_slice_type_falls_back_to_default_when_key_absent(self, tmp_path):
        text = """\
            pipeline:
              plan-review:
                rounds: 3
                default: g3flash-x3-sonnetmax
                holistic: sonnetmax
        """
        cfg = load(write_yaml(tmp_path, text))
        # per-card key is absent → falls back to default
        assert resolve_reviewer_name(cfg, "plan", 1, slice_type="per-card") == "g3flash-x3-sonnetmax"

    def test_slice_type_raises_when_no_default_and_key_absent(self, tmp_path):
        text = """\
            pipeline:
              plan-review:
                rounds: 3
                holistic: sonnetmax
        """
        cfg = load(write_yaml(tmp_path, text))
        with pytest.raises(ConfigError):
            resolve_reviewer_name(cfg, "plan", 1, slice_type="per-card")


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
