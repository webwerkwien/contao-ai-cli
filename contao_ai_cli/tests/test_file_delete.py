"""`file delete` keeps the server's answer — above all the list of usages.

Measured on c5 on 2026-09-16, before release: a refused delete printed only
*"Error: Command failed (exit 1): … is still used in 4 place(s)"*, even with --json.
The ``usages`` the core-bundle sends — which element uses the file — were dropped, so a
caller knew *that* it was used but not *where*. The answer is now written as it came,
and the exit code still says the file was not deleted.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_file import file_delete_cmd
from contao_ai_cli.core.file import file_delete

REFUSED = {
    "status": "error",
    "message": "files/conpai/a.png is still used in 1 place(s). Nothing was deleted.",
    "usages": [{"table": "tl_content", "id": 650, "field": "singleSRC", "path": "files/conpai/a.png"}],
    "code": 1,
}


def _backend(payload: dict, returncode: int) -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps(payload), "returncode": returncode, "stderr": ""}
    return backend


def test_a_refusal_is_returned_with_its_usages_instead_of_raised():
    result = file_delete(_backend(REFUSED, 1), "files/conpai/a.png")

    assert result["usages"][0]["id"] == 650
    assert result["status"] == "error"


def test_the_command_is_run_without_raising_on_the_exit_code():
    backend = _backend(REFUSED, 1)
    file_delete(backend, "files/conpai/a.png")

    assert backend.run.call_args.kwargs.get("check") is False


def test_the_cli_prints_the_usages_and_exits_non_zero():
    with patch("contao_ai_cli.cli.cli_file._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_file._get_backend", return_value=_backend(REFUSED, 1)):
        result = CliRunner().invoke(file_delete_cmd, ["--path", "files/conpai/a.png", "--yes", "--json"], obj={})

    assert result.exit_code == 1
    assert json.loads(result.stdout)["usages"][0]["table"] == "tl_content"


def test_a_deletion_exits_zero():
    ok = {"status": "ok", "path": "files/conpai/a.png", "type": "file", "deleted": True}
    with patch("contao_ai_cli.cli.cli_file._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_file._get_backend", return_value=_backend(ok, 0)):
        result = CliRunner().invoke(file_delete_cmd, ["--path", "files/conpai/a.png", "--yes", "--json"], obj={})

    assert result.exit_code == 0
    assert json.loads(result.stdout)["deleted"] is True


def test_output_that_is_no_json_still_fails_loudly():
    backend = MagicMock()
    backend.run.return_value = {"stdout": "PHP Fatal error", "returncode": 255, "stderr": "boom"}

    try:
        file_delete(backend, "files/conpai/a.png")
    except Exception as e:  # noqa: BLE001 - the type is the backend's own error
        assert "255" in str(e)
    else:
        raise AssertionError("a failed run without JSON must raise")
