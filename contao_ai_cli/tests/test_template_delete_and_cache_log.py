"""`template delete` (Nr. 51) and a logged `cache clear` (Nr. 50) -- ConpAI 1.0 acceptance test.

Cleaning up c5 on 2026-09-17 needed `ssh rm` for two template variants: the CLI could list,
read and write templates, not delete them. And the audit of phase 5 found every step in
`tl_log` except `cache clear`, which ran Symfony's `cache:clear` without a trace.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli.cli_template import template_delete_cmd
from contao_ai_cli.core import cache as cache_mod
from contao_ai_cli.core import template as template_mod
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError


def _backend(payload, returncode=0, stderr=""):
    b = MagicMock()
    b.run.return_value = {"stdout": json.dumps(payload) if isinstance(payload, dict) else payload,
                          "returncode": returncode, "stderr": stderr}
    b.undefined_command_hint.return_value = ""
    return b


def test_template_delete_calls_the_core_command_quoted():
    b = _backend({"status": "ok", "path": "templates/content_element/text/a b.html.twig", "deleted": True})
    template_mod.template_delete(b, "templates/content_element/text/a b.html.twig")
    assert b.run.call_args.args[0] == "contao:template:delete --path 'templates/content_element/text/a b.html.twig'"


def test_template_delete_needs_yes_without_an_answer():
    """Irreversible like file delete: silence at the prompt is a no."""
    b = _backend({"status": "ok"})
    with patch("contao_ai_cli.cli.cli_template._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_template._get_backend", return_value=b), \
         patch("contao_ai_cli.cli.cli_template.confirm_escalation", return_value=False):
        result = CliRunner().invoke(template_delete_cmd, ["--path", "templates/x/y/z.html.twig", "--json"], obj={})
    assert result.exit_code == 1
    assert "--yes" in json.loads(result.stdout)["message"]
    b.run.assert_not_called()


def test_template_delete_error_exits_non_zero_with_the_answer():
    refused = {"status": "error", "message": "Template not found: templates/x.html.twig. Nothing was deleted.", "code": 1}
    with patch("contao_ai_cli.cli.cli_template._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_template._get_backend", return_value=_backend(refused, 1)):
        result = CliRunner().invoke(template_delete_cmd, ["--path", "templates/x.html.twig", "--yes", "--json"], obj={})
    assert result.exit_code == 1
    assert "not found" in json.loads(result.stdout)["message"]


def test_cache_clear_uses_the_logged_core_command():
    b = _backend({"status": "ok", "cleared": True, "logged": True, "output": "[OK] cleared"})
    result = cache_mod.cache_clear(b)
    assert b.run.call_args.args[0] == "contao:cache:clear"
    assert result == {"status": "cleared", "output": "[OK] cleared", "logged": True}


def test_cache_clear_falls_back_on_an_old_core_bundle():
    b = MagicMock()
    b.run.side_effect = [
        {"stdout": "", "returncode": 1, "stderr": 'Command "contao:cache:clear" is not defined.'},
        {"stdout": "[OK] Cache cleared.", "returncode": 0, "stderr": ""},
    ]
    b.undefined_contao_command.return_value = "contao:cache:clear"
    result = cache_mod.cache_clear(b)
    assert [c.args[0] for c in b.run.call_args_list] == ["contao:cache:clear", "cache:clear"]
    assert result["status"] == "cleared" and result["logged"] is False


def test_cache_clear_fallback_recognises_what_an_old_bundle_really_says():
    """Without the mock: Contao has no contao:cache:* of its own, so Symfony names the namespace."""
    b = MagicMock()
    b.run.side_effect = [
        {"stdout": "", "returncode": 1,
         "stderr": 'There are no commands defined in the "contao:cache" namespace.'},
        {"stdout": "[OK] Cache cleared.", "returncode": 0, "stderr": ""},
    ]
    b.undefined_contao_command.side_effect = ContaoBackend.undefined_contao_command
    result = cache_mod.cache_clear(b)
    assert result["logged"] is False


def test_cache_clear_failure_names_the_core_message_not_a_cut_json():
    """Fable review before v0.22.0: `stdout[:500]` could cut the answer mid-document."""
    message = "cache:clear failed: " + "x" * 600
    b = _backend({"status": "error", "message": message, "code": 1}, returncode=1)
    b.undefined_contao_command.return_value = None
    with pytest.raises(ContaoBackendError) as err:
        cache_mod.cache_clear(b)
    assert str(err.value).endswith(message)
