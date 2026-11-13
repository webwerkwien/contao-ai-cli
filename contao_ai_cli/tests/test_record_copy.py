"""`article copy`, `content copy`: the back end's copy and paste (core-bundle v1.17.0).

Without a target the copy goes directly behind the source, which is what "duplicate"
means; `--after` puts it behind another record, `--to` behind the last child of a
parent. The server copies every field and the children and answers with the new ID.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli.cli_article import article_copy_cmd
from contao_ai_cli.cli.cli_content import content_copy_cmd
from contao_ai_cli.core.contao_ops import run_move
from contao_ai_cli.utils.contao_backend import ContaoBackendError

COPIED = {"status": "ok", "id": 100, "sourceId": 40, "pid": 7, "ptable": "tl_article",
          "sorting": 192, "children": 3, "notCopied": []}


def _backend(payload: dict, returncode: int = 0) -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps(payload), "returncode": returncode, "stderr": ""}
    backend.undefined_command_hint.return_value = ""
    return backend


@pytest.mark.parametrize("command, named", [
    ("contao:content:copy", "content copy failed"),
    ("contao:article:copy", "article copy failed"),
    ("contao:content:move", "content move failed"),
])
def test_a_failure_without_json_names_the_command_and_the_version_it_needs(command, named):
    # An older core has no copy command: Symfony answers on stderr, not in JSON.
    backend = MagicMock()
    backend.run.return_value = {"stdout": "", "returncode": 1, "stderr": f'Command "{command}" is not defined.'}
    backend.undefined_command_hint.return_value = "\nneeds core-bundle v1.17.0"

    with pytest.raises(ContaoBackendError) as raised:
        run_move(backend, command, 40)

    assert named in str(raised.value)
    assert "needs core-bundle v1.17.0" in str(raised.value)


def test_without_a_target_only_the_id_goes_to_the_server():
    backend = _backend(COPIED)
    run_move(backend, "contao:content:copy", 40)

    assert backend.run.call_args.args[0] == "contao:content:copy 40 --no-interaction"


@pytest.mark.parametrize("command, module, args, sent", [
    (content_copy_cmd, "cli_content", ["40", "--json"], "contao:content:copy 40 --no-interaction"),
    (content_copy_cmd, "cli_content", ["40", "--to", "12", "--ptable", "tl_news", "--json"],
     "contao:content:copy 40 --to=12 --ptable=tl_news --no-interaction"),
    (article_copy_cmd, "cli_article", ["7", "--after", "9", "--json"], "contao:article:copy 7 --after=9 --no-interaction"),
    (article_copy_cmd, "cli_article", ["7", "--to", "4", "--json"], "contao:article:copy 7 --to=4 --no-interaction"),
    # The operator's back-end language marks the copy, and a copied article belongs to them.
    (content_copy_cmd, "cli_content", ["40", "--operator", "k.editor", "--json"],
     "contao:content:copy 40 --operator=k.editor --no-interaction"),
    (article_copy_cmd, "cli_article", ["7", "--operator", "anna maria", "--json"],
     "contao:article:copy 7 --operator='anna maria' --no-interaction"),
])
def test_a_copy_prints_the_answer_and_exits_zero(command, module, args, sent):
    backend = _backend(COPIED)
    with patch(f"contao_ai_cli.cli.{module}._require_core_bundle"), \
         patch(f"contao_ai_cli.cli.{module}._get_backend", return_value=backend):
        result = CliRunner().invoke(command, args, obj={})

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["id"] == 100
    assert backend.run.call_args.args[0] == sent


def test_a_refusal_keeps_its_message_and_exits_non_zero():
    refused = {"status": "error", "code": 1,
               "message": "A tl_content record cannot be copied into itself or one of its own elements"}
    with patch("contao_ai_cli.cli.cli_content._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_content._get_backend", return_value=_backend(refused, 1)):
        result = CliRunner().invoke(content_copy_cmd, ["40", "--to", "40", "--ptable", "tl_content", "--json"], obj={})

    assert result.exit_code == 1
    assert "into itself" in json.loads(result.stdout)["message"]


@pytest.mark.parametrize("command, module, args, named", [
    (content_copy_cmd, "cli_content", ["40", "--to", "12", "--after", "38"], "--after"),
    (content_copy_cmd, "cli_content", ["40", "--after", "38", "--ptable", "tl_news"], "--ptable"),
    (content_copy_cmd, "cli_content", ["40", "--ptable", "tl_news"], "--ptable"),
    (article_copy_cmd, "cli_article", ["7", "--to", "4", "--after", "9"], "--after"),
])
def test_usage_errors_reach_no_server(command, module, args, named):
    with patch(f"contao_ai_cli.cli.{module}._require_core_bundle"), \
         patch(f"contao_ai_cli.cli.{module}._get_backend") as backend:
        result = CliRunner().invoke(command, args, obj={})

    assert result.exit_code == 2
    assert named in result.output
    backend.assert_not_called()
