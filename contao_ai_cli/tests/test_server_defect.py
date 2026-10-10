"""A crash on the server gets a report; a refusal stays a message (v1.3.0).

Since core-bundle v1.3.0 an error answer that comes from a defect carries
`"exception": "<ShortClassName>"`. Up to then a failed query and "page not found"
arrived as the same `ContaoBackendError`, and neither offered a report -- while a
bridge answering 500 did. The backend bundle's chat had the same gap and closed it
in v0.12.0.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from contao_ai_cli import contao_cli
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError

REFUSAL = {"status": "error", "code": 1,
           "message": "InvalidArgumentException: Only a website root (type root) can stand at the top level."}
DEFECT = {"status": "error", "code": 1, "exception": "DriverException",
          "message": "DriverException: An exception occurred while executing a query"}


def failing_run(answer: dict) -> ContaoBackendError:
    backend = ContaoBackend.__new__(ContaoBackend)
    backend.contao_root = "/var/www"
    backend.php_path = "php"
    with patch.object(ContaoBackend, "_ssh_args", return_value=["ssh"]), \
         patch.object(ContaoBackend, "_guard_command_line_length"), \
         patch("contao_ai_cli.utils.contao_backend.subprocess.run",
               return_value=MagicMock(returncode=1, stdout=json.dumps(answer), stderr="")):
        with pytest.raises(ContaoBackendError) as e:
            backend.run("contao:page:create --title x")
    return e.value


def test_run_names_the_defect_the_core_marked():
    assert failing_run(DEFECT).defect == "DriverException"


def test_a_refusal_and_an_older_core_name_none():
    assert failing_run(REFUSAL).defect is None


def test_cache_clear_keeps_the_defect():
    """Second review: `cache clear` runs with check=False and raised its own error,
    without the field -- a crashed `contao:cache:clear` got no report."""
    from contao_ai_cli.core import cache

    backend = MagicMock()
    backend.run.return_value = {"returncode": 1, "stderr": "", "stdout": json.dumps(
        {"status": "error", "code": 1, "exception": "RuntimeException", "message": "RuntimeException: disk full"})}
    backend.undefined_contao_command.return_value = None

    with pytest.raises(ContaoBackendError) as e:
        cache.cache_clear(backend)
    assert e.value.defect == "RuntimeException"
    assert "disk full" in str(e.value.message)


def test_user_create_keeps_the_defect_of_the_password_step():
    from contao_ai_cli.core import user

    backend = MagicMock()
    backend.run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    with patch.object(user, "user_password",
                      side_effect=ContaoBackendError("DriverException: …", defect="DriverException")):
        with pytest.raises(ContaoBackendError) as e:
            user.user_create(backend, "probe", "a long probe password", "Probe", "probe@example.org")
    assert e.value.defect == "DriverException"
    assert "was created" in str(e.value.message)


def main_with(monkeypatch, argv, error):
    def fake_cli(*args, **kwargs):
        raise error

    monkeypatch.setattr(contao_cli, "cli", fake_cli)
    monkeypatch.setattr(contao_cli.sys, "argv", ["contao-ai-cli", *argv])
    with pytest.raises(SystemExit) as exit_info:
        contao_cli.main()
    return exit_info.value.code


def test_a_server_defect_gets_a_report(monkeypatch, capsys):
    code = main_with(monkeypatch, ["page", "create"],
                     ContaoBackendError("Command failed (exit 1): DriverException: …", defect="DriverException"))

    out, err = capsys.readouterr()
    assert code == 1
    assert "Error: Command failed" in err
    assert "## Fehlerbericht contao-ai" in err
    assert "| ausnahme.server | `DriverException` |" in err
    assert out == "", "the report goes to stderr, stdout stays parseable"


def test_a_refusal_gets_no_report(monkeypatch, capsys):
    main_with(monkeypatch, ["page", "create"], ContaoBackendError("Command failed (exit 1): InvalidArgumentException: …"))

    assert "Fehlerbericht" not in capsys.readouterr().err


def test_under_json_the_answer_names_the_exception(monkeypatch, capsys):
    main_with(monkeypatch, ["--json", "page", "create"],
              ContaoBackendError("Command failed (exit 1): DriverException: …", defect="DriverException"))

    out, err = capsys.readouterr()
    assert json.loads(out)["exception"] == "DriverException"
    assert "## Fehlerbericht contao-ai" in err


def test_under_json_a_refusal_has_no_exception_field(monkeypatch, capsys):
    main_with(monkeypatch, ["--json", "page", "create"], ContaoBackendError("Page not found: 198"))

    assert "exception" not in json.loads(capsys.readouterr().out)
