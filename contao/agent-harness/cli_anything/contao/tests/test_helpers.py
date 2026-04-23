"""
Unit tests for contao_ops helper functions.
Tests for run_sql_table, run_json_or_raw, and build_set_args.
"""
import json
from unittest.mock import MagicMock, patch
import pytest

from cli_anything.contao.core.contao_ops import (
    run_sql_table, run_json_or_raw, build_set_args
)


class TestRunSqlTable:
    def test_run_sql_table_returns_list(self):
        """Test that run_sql_table parses table output into a list of dicts."""
        backend = MagicMock()
        backend.run.return_value = {"stdout": " id | title \n----+-------\n  1 | Foo   \n"}
        with patch("cli_anything.contao.core.contao_ops.parse_table", return_value=[{"id": "1", "title": "Foo"}]):
            result = run_sql_table(backend, "SELECT id, title FROM tl_article")
        assert result == [{"id": "1", "title": "Foo"}]
        backend.run.assert_called_once()

    def test_run_sql_table_returns_empty_list_on_no_rows(self):
        """Test that run_sql_table returns empty list when no rows are returned."""
        backend = MagicMock()
        backend.run.return_value = {"stdout": ""}
        with patch("cli_anything.contao.core.contao_ops.parse_table", return_value=None):
            result = run_sql_table(backend, "SELECT id FROM tl_article WHERE id = 9999")
        assert result == []


class TestRunJsonOrRaw:
    def test_run_json_or_raw_parses_json(self):
        """Test that run_json_or_raw parses valid JSON output."""
        backend = MagicMock()
        backend.run.return_value = {"stdout": '{"status": "ok"}'}
        result = run_json_or_raw(backend, "contao:article:read 1")
        assert result == {"status": "ok"}

    def test_run_json_or_raw_falls_back_to_raw(self):
        """Test that run_json_or_raw falls back to raw string on JSON parse error."""
        backend = MagicMock()
        backend.run.return_value = {"stdout": "not json"}
        result = run_json_or_raw(backend, "contao:article:read 1")
        assert result == {"raw": "not json"}


class TestBuildSetArgs:
    def test_build_set_args_empty(self):
        """Test that build_set_args returns empty string for empty dict."""
        assert build_set_args({}) == ""

    def test_build_set_args_escapes_special_chars(self):
        """Test that build_set_args escapes special characters properly."""
        result = build_set_args({"email": "foo@bar.com", "name": "O'Hara"})
        assert "--set" in result
        assert "foo@bar.com" in result
        # Both keys should be in the result
        assert "email" in result
        assert "name" in result
