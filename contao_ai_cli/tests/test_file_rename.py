"""`file rename --path … --name …`: rename in place, UUID kept.

The gap: files and folders could be moved but not renamed. Deleting and writing under a
new name changes the UUID, and every image element pointing at it renders nothing. The
core-bundle command keeps the UUIDs and reports `pathUsages`, as `file move` does.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_file import file_rename_cmd
from contao_ai_cli.core.file import file_rename

RENAMED = {
    "status": "ok", "path": "files/media/logo.svg", "to": "files/media/logo-2026.svg",
    "name": "logo-2026.svg", "type": "file", "records": 1, "uuidsKept": True,
    "pathUsages": [{"table": "tl_content", "id": 7, "field": "text", "path": "files/media/logo.svg"}],
}


def _backend(payload: dict, returncode: int = 0) -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps(payload), "returncode": returncode, "stderr": ""}
    backend.undefined_command_hint.return_value = ""
    return backend


def _invoke(backend, args):
    with patch("contao_ai_cli.cli.cli_file._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_file._get_backend", return_value=backend):
        return CliRunner().invoke(file_rename_cmd, args, obj={})


def test_path_and_name_are_quoted_into_the_server_command():
    backend = _backend(RENAMED)
    file_rename(backend, "files/media/logo one.svg", "logo 2026.svg")

    assert backend.run.call_args.args[0] == (
        "contao:file:rename --path 'files/media/logo one.svg' --name 'logo 2026.svg'"
    )


def test_a_rename_prints_the_path_usages_and_exits_zero():
    result = _invoke(_backend(RENAMED), ["--path", "files/media/logo.svg", "--name", "logo-2026.svg", "--json"])

    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["uuidsKept"] is True
    assert out["pathUsages"][0]["id"] == 7


def test_a_refusal_keeps_its_message_and_exits_non_zero():
    refused = {"status": "error", "message": "files/media/b.png already exists. Nothing was renamed.", "code": 1}
    result = _invoke(_backend(refused, 1), ["--path", "files/media/a.png", "--name", "b.png", "--json"])

    assert result.exit_code == 1
    assert "already exists" in json.loads(result.stdout)["message"]


def test_a_non_json_failure_names_the_command_and_the_exit():
    backend = MagicMock()
    backend.run.return_value = {"stdout": "", "returncode": 255, "stderr": "ssh: connection refused"}
    backend.undefined_command_hint.return_value = ""

    try:
        file_rename(backend, "files/a.png", "b.png")
    except Exception as e:  # ContaoBackendError
        assert "file rename failed (exit 255)" in str(e)
    else:
        raise AssertionError("expected an error")


def test_both_options_are_required():
    for args in (["--name", "b.png"], ["--path", "files/a.png"]):
        result = _invoke(_backend(RENAMED), args)
        assert result.exit_code != 0
