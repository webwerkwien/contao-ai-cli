"""Errors under --json come back as JSON on stdout (v0.28.0).

The guide promised it for a long time; Click printed `Error: ...` itself
before `--json` had a say. Found by the second agent test on 2026-09-18:
`page read 198 --json` after a delete answered in plain text.
"""
import json

import click
import pytest

from contao_ai_cli import contao_cli
from contao_ai_cli.utils.contao_backend import ContaoBackendError


def _run(monkeypatch, argv, raises=None, returns=None):
    def fake_cli(*args, **kwargs):
        if raises is not None:
            raise raises
        return returns

    monkeypatch.setattr(contao_cli, "cli", fake_cli)
    monkeypatch.setattr(contao_cli.sys, "argv", ["contao-ai-cli", *argv])
    with pytest.raises(SystemExit) as exit_info:
        contao_cli.main()
    return exit_info.value.code


def test_backend_error_under_json_is_one_object_on_stdout(monkeypatch, capsys):
    code = _run(monkeypatch, ["--json", "page", "read", "198"],
                raises=ContaoBackendError("Page not found: 198"))

    out, err = capsys.readouterr()
    assert code == 1
    assert json.loads(out) == {"status": "error", "code": 1, "message": "Page not found: 198"}
    assert err == ""


def test_the_command_level_flag_counts_too(monkeypatch, capsys):
    """`page read 198 --json` -- the form the agent used -- not only `--json page ...`."""
    _run(monkeypatch, ["page", "read", "198", "--json"],
         raises=ContaoBackendError("Page not found: 198"))

    assert json.loads(capsys.readouterr().out)["message"] == "Page not found: 198"


def test_without_json_the_error_line_stays_on_stderr(monkeypatch, capsys):
    code = _run(monkeypatch, ["page", "read", "198"],
                raises=ContaoBackendError("Page not found: 198"))

    out, err = capsys.readouterr()
    assert code == 1
    assert out == ""
    assert "Error: Page not found: 198" in err


def test_usage_error_keeps_exit_code_2(monkeypatch, capsys):
    code = _run(monkeypatch, ["--json", "page", "read"],
                raises=click.UsageError("Missing argument 'PAGE_ID'."))

    assert code == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "error", "code": 2, "message": "Missing argument 'PAGE_ID'."}


def test_abort_under_json(monkeypatch, capsys):
    code = _run(monkeypatch, ["--json", "page", "delete", "5"], raises=click.Abort())

    assert code == 1
    assert json.loads(capsys.readouterr().out)["message"] == "Aborted!"


def test_unexpected_failure_under_json_still_gets_its_report(monkeypatch, capsys):
    code = _run(monkeypatch, ["--json", "health"], raises=RuntimeError("unerwartet"))

    out, err = capsys.readouterr()
    assert code == 1
    assert json.loads(out) == {"status": "error", "code": 1, "message": "unerwartet"}
    assert "Fehlerbericht contao-ai" in err


def test_json_after_double_dash_is_a_value(monkeypatch, capsys):
    _run(monkeypatch, ["ext", "run", "demo", "--", "--json"],
         raises=ContaoBackendError("failed"))

    out, err = capsys.readouterr()
    assert out == ""
    assert "Error: failed" in err


def test_ctx_exit_code_is_passed_on(monkeypatch):
    """main() turns a returned int into the exit code.

    Non-standalone Click returns `ctx.exit(1)` as a value instead of exiting;
    this stands in for that return, it does not drive a real ctx.exit().
    """
    assert _run(monkeypatch, ["bundle", "update", "core"], returns=1) == 1


def test_success_does_not_exit(monkeypatch):
    monkeypatch.setattr(contao_cli, "cli", lambda *a, **k: None)
    monkeypatch.setattr(contao_cli.sys, "argv", ["contao-ai-cli", "--json", "health"])
    contao_cli.main()  # no SystemExit


def test_real_cli_usage_error_arrives_as_json(monkeypatch, capsys, tmp_path):
    """Through the real command tree: for a core-bundle command a missing
    session file is a usage error (exit 2)."""
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(contao_cli.sys, "argv",
                        ["contao-ai-cli", "--session", str(missing), "--json", "page", "read", "1"])
    with pytest.raises(SystemExit) as exit_info:
        contao_cli.main()

    answer = json.loads(capsys.readouterr().out)
    assert exit_info.value.code == 2
    assert answer["status"] == "error"
    assert answer["code"] == 2
    assert "nope.json" in answer["message"]


def test_real_cli_backend_error_from_get_backend_arrives_as_json(monkeypatch, capsys, tmp_path):
    """`cache clear` needs no core bundle, so the missing session surfaces in
    _get_backend() -- which printed its own `[ERROR]` line until v0.28.0."""
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(contao_cli.sys, "argv",
                        ["contao-ai-cli", "--session", str(missing), "--json", "cache", "clear"])
    with pytest.raises(SystemExit) as exit_info:
        contao_cli.main()

    out, err = capsys.readouterr()
    answer = json.loads(out)
    assert exit_info.value.code == 1
    assert answer["code"] == 1
    assert "Session file not found" in answer["message"]
    assert err == ""
