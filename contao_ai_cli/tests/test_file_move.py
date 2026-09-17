"""`file move --path … --to <folder>`: move as cut and paste in the back end, UUID kept.

Live on web.werk.wien on 2026-09-17 (ConpAI 1.0, Nr. 64): the site's files were to go
into `files/conpai-consho/layout`, and there was no way to move a file. Deleting and
writing anew changes the UUID, and every image element pointing at it renders nothing.
The core-bundle command (v0.23.0) keeps the UUIDs and reports `pathUsages` — texts that
name the old path, which a move does break.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_file import file_move_cmd
from contao_ai_cli.core.file import file_move

MOVED = {
    "status": "ok", "path": "files/conpai/bot.svg", "to": "files/conpai-consho/layout/bot.svg",
    "type": "file", "records": 1, "uuidsKept": True,
    "pathUsages": [{"table": "tl_content", "id": 711, "field": "text", "path": "files/conpai/bot.svg"}],
}


def _backend(payload: dict, returncode: int = 0) -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps(payload), "returncode": returncode, "stderr": ""}
    backend.undefined_command_hint.return_value = ""
    return backend


def test_the_paths_are_quoted_into_the_server_command():
    backend = _backend(MOVED)
    file_move(backend, "files/conpai/bot one.svg", "files/conpai-consho/layout")

    cmd = backend.run.call_args.args[0]
    assert cmd == "contao:file:move --path 'files/conpai/bot one.svg' --to files/conpai-consho/layout"


def test_a_refusal_is_returned_with_its_message_and_exits_non_zero():
    refused = {"status": "error", "message": "files/y/a.png already exists. Nothing was moved.", "code": 1}
    with patch("contao_ai_cli.cli.cli_file._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_file._get_backend", return_value=_backend(refused, 1)):
        result = CliRunner().invoke(file_move_cmd, ["--path", "files/x/a.png", "--to", "files/y", "--json"], obj={})

    assert result.exit_code == 1
    assert "already exists" in json.loads(result.stdout)["message"]


def test_a_move_prints_the_path_usages_and_exits_zero():
    with patch("contao_ai_cli.cli.cli_file._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_file._get_backend", return_value=_backend(MOVED)):
        result = CliRunner().invoke(file_move_cmd, ["--path", "files/conpai/bot.svg", "--to", "files/conpai-consho/layout", "--json"], obj={})

    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["uuidsKept"] is True
    assert out["pathUsages"][0]["id"] == 711
