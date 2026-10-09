"""`page move`, `article move`, `content move`: the back end's cut and paste (core-bundle v1.2.0).

People say "put it below X" or "after X". `--to` is the first: behind the last child of
X. `--after` the second: directly behind X, below X's parent. Before v1.2.0 a record
could only be moved with `update --set pid=…`, which nobody looking for "move" found and
which put it wherever its old sorting fell (core-bundle, fixed in the same release).

The server computes the position and runs every rule of an update: parent check, no
move below itself, the page tree rules (a root only at the top level), version, cache.
Prompted by Contao's 6.1 API gaining the same operation (contao/contao#10400).
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli.cli_article import article_move_cmd
from contao_ai_cli.cli.cli_content import content_move_cmd
from contao_ai_cli.cli.cli_page import page_move_cmd
from contao_ai_cli.core.contao_ops import run_move

MOVED = {"status": "ok", "id": 12, "pid": 3, "sorting": 192,
         "cacheTags": ["contao.db.tl_page.12", "contao.db.tl_page.3", "contao.db.tl_page.7"]}


def _backend(payload: dict, returncode: int = 0) -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps(payload), "returncode": returncode, "stderr": ""}
    backend.undefined_command_hint.return_value = ""
    return backend


def test_to_becomes_the_server_option():
    backend = _backend(MOVED)
    run_move(backend, "contao:page:move", 12, to=3)

    assert backend.run.call_args.args[0] == "contao:page:move 12 --to=3 --no-interaction"


def test_after_becomes_the_server_option():
    backend = _backend(MOVED)
    run_move(backend, "contao:page:move", 12, after=5)

    assert backend.run.call_args.args[0] == "contao:page:move 12 --after=5 --no-interaction"


def test_content_passes_the_parent_table_quoted():
    backend = _backend(MOVED)
    run_move(backend, "contao:content:move", 30, to=8, ptable="tl_news")

    assert backend.run.call_args.args[0] == "contao:content:move 30 --to=8 --ptable=tl_news --no-interaction"


@pytest.mark.parametrize("command, module, args", [
    (page_move_cmd, "cli_page", ["12", "--to", "3", "--json"]),
    (article_move_cmd, "cli_article", ["12", "--after", "5", "--json"]),
    (content_move_cmd, "cli_content", ["12", "--to", "8", "--ptable", "tl_news", "--json"]),
])
def test_a_move_prints_the_answer_and_exits_zero(command, module, args):
    with patch(f"contao_ai_cli.cli.{module}._require_core_bundle"), \
         patch(f"contao_ai_cli.cli.{module}._get_backend", return_value=_backend(MOVED)):
        result = CliRunner().invoke(command, args, obj={})

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["sorting"] == 192


def test_a_refusal_keeps_its_message_and_exits_non_zero():
    refused = {"status": "error", "code": 1,
               "message": "InvalidArgumentException: Only a website root (type root) can stand at the top level"}
    with patch("contao_ai_cli.cli.cli_page._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_page._get_backend", return_value=_backend(refused, 1)):
        result = CliRunner().invoke(page_move_cmd, ["12", "--to", "0", "--json"], obj={})

    assert result.exit_code == 1
    assert "website root" in json.loads(result.stdout)["message"]


@pytest.mark.parametrize("args", [["12"], ["12", "--to", "3", "--after", "5"]])
def test_exactly_one_of_to_and_after(args):
    with patch("contao_ai_cli.cli.cli_page._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_page._get_backend") as backend:
        result = CliRunner().invoke(page_move_cmd, args, obj={})

    assert result.exit_code == 2
    assert "--to" in result.output and "--after" in result.output
    backend.assert_not_called()


def test_ptable_only_with_to():
    with patch("contao_ai_cli.cli.cli_content._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_content._get_backend") as backend:
        result = CliRunner().invoke(content_move_cmd, ["12", "--after", "5", "--ptable", "tl_news"], obj={})

    assert result.exit_code == 2
    assert "--ptable" in result.output
    backend.assert_not_called()


def test_a_missing_server_command_names_the_version():
    backend = MagicMock()
    backend.run.return_value = {"stdout": "", "returncode": 1,
                                "stderr": 'Command "contao:page:move" is not defined.'}
    backend.undefined_command_hint.return_value = "\nNeeds contao-ai-core-bundle v1.2.0"

    with pytest.raises(Exception, match="v1.2.0"):
        run_move(backend, "contao:page:move", 12, to=3)
