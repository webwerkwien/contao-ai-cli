"""`template rename` -- the CLI side of contao:template:rename (core-bundle v1.15.0).

Templates are named, not referenced by UUID: writing a variant anew and deleting the old
one reset every element using it to the default template. The core renames the variant
as the Template Studio does and carries the records along; the CLI passes its answer on.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli.cli_template import template_rename_cmd
from contao_ai_cli.core import template as template_mod
from contao_ai_cli.utils.contao_backend import ContaoBackendError


def _backend(payload, returncode=0, stderr=""):
    b = MagicMock()
    b.run.return_value = {"stdout": json.dumps(payload) if isinstance(payload, dict) else payload,
                          "returncode": returncode, "stderr": stderr}
    b.undefined_command_hint.return_value = ""
    return b


def _invoke(b, args):
    with patch("contao_ai_cli.cli.cli_template._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_template._get_backend", return_value=b):
        return CliRunner().invoke(template_rename_cmd, args, obj={})


def test_template_rename_calls_the_core_command_quoted():
    b = _backend({"status": "ok"})
    template_mod.template_rename(b, "templates/content_element/text/a b.html.twig", "my teaser")
    assert b.run.call_args.args[0] == (
        "contao:template:rename --path 'templates/content_element/text/a b.html.twig' --name='my teaser'"
    )
    assert b.run.call_args.kwargs == {"check": False}


def test_template_rename_keeps_a_name_beginning_with_a_dash_as_the_value():
    b = _backend({"status": "ok"})
    template_mod.template_rename(b, "templates/content_element/text/a.html.twig", "-b")
    assert b.run.call_args.args[0] == (
        "contao:template:rename --path templates/content_element/text/a.html.twig --name=-b"
    )


def test_template_rename_passes_the_answer_on():
    answer = {"status": "ok", "path": "templates/content_element/text/hero.html.twig",
              "to": "templates/content_element/text/teaser.html.twig",
              "identifier": "content_element/text/hero", "newIdentifier": "content_element/text/teaser",
              "migratedUsages": {"table": "tl_content", "field": "customTpl", "ids": [7, 8]}}
    result = _invoke(_backend(answer), ["--path", answer["path"], "--name", "teaser", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == answer


def test_template_rename_refusal_exits_non_zero_with_its_message():
    refused = {"status": "error", "message": "templates/content_element/text.html.twig is no variant of a "
               "content element, front-end module or page. Nothing was renamed.", "code": 1}
    result = _invoke(_backend(refused, 1), ["--path", "templates/content_element/text.html.twig",
                                            "--name", "teaser", "--json"])
    assert result.exit_code == 1
    assert "no variant" in json.loads(result.stdout)["message"]


def test_template_rename_names_command_and_exit_code_when_the_answer_is_no_json():
    b = _backend("PHP Fatal error: something broke", 255)
    with pytest.raises(ContaoBackendError, match=r"template rename failed \(exit 255\)"):
        template_mod.template_rename(b, "templates/content_element/text/hero.html.twig", "teaser")


@pytest.mark.parametrize("missing", ["--path", "--name"])
def test_template_rename_needs_both_options(missing):
    args = {"--path": "templates/content_element/text/hero.html.twig", "--name": "teaser"}
    del args[missing]
    result = _invoke(_backend({"status": "ok"}), [x for kv in args.items() for x in kv])
    assert result.exit_code == 2
    assert missing in result.output
