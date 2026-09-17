"""Updates are mentioned when a new working block starts — on stderr, never in an answer."""
import json

import pytest

from contao_ai_cli.core import update_notice as un

H = 3600


@pytest.fixture(autouse=True)
def _notice_enabled(monkeypatch):
    # conftest.py switches the notice off for every other test; these tests need it on.
    # Module fixtures run after conftest fixtures, so this delenv wins.
    monkeypatch.delenv("CONTAO_AI_CLI_NO_UPDATE_CHECK", raising=False)
STATE = {"cli": {"installed": "0.21.0", "latest": "0.22.0", "up_to_date": False},
         "core": {"reachable": True, "installed": "v0.18.0", "latest": "0.19.0", "update_available": True},
         "backend": {"installed": None, "latest": "0.3.0", "update_available": False}}


def test_never_checked_is_due():
    assert un.is_due({}, now=1000 * H)


def test_a_pause_of_more_than_12_hours_is_due():
    assert un.is_due({"lastCommandAt": 0, "lastCheckAt": 0}, now=13 * H)


def test_working_on_is_not_due():
    assert not un.is_due({"lastCommandAt": 11 * H, "lastCheckAt": 1 * H}, now=12 * H)


def test_continuous_use_is_still_checked_every_24_hours():
    assert un.is_due({"lastCommandAt": 24 * H, "lastCheckAt": 0}, now=24 * H + 60)


def test_the_notice_lists_every_update_in_ascii():
    text = un.format_notice(STATE)
    assert "CLI 0.21.0 -> 0.22.0" in text and "core-bundle v0.18.0 -> 0.19.0" in text
    assert text.isascii()


def test_nothing_to_update_is_no_notice():
    quiet = {"cli": {"up_to_date": True}, "core": {"reachable": True, "update_available": False},
             "backend": {"update_available": False}}
    assert un.format_notice(quiet) is None


def test_after_command_checks_once_and_writes_to_stderr_only(tmp_path):
    lines = []
    calls = []
    state_file = tmp_path / "state" / "update-check.json"

    def collect(path):
        calls.append(path)
        return STATE

    for now in (0, 60, 120):
        un.after_command("s.json", "page", now=now, state_file=str(state_file),
                         collect=collect, echo=lambda m: lines.append(m))
    assert len(calls) == 1 and len(lines) == 1
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["sessions"]["s.json"]["lastCommandAt"] == 120


def test_a_failed_check_counts_as_a_check(tmp_path):
    state_file = tmp_path / "state" / "update-check.json"

    def boom(path):
        raise RuntimeError("offline")

    un.after_command("s.json", "page", now=0, state_file=str(state_file), collect=boom, echo=lambda m: None)
    assert json.loads(state_file.read_text(encoding="utf-8"))["sessions"]["s.json"]["lastCheckAt"] == 0


def test_opt_out_and_skipped_commands(tmp_path, monkeypatch):
    calls = []
    state_file = str(tmp_path / "u.json")
    for command in ("health", "self-update", "bundle", "connect", "repl",
                    "session-list", "session-delete", None):
        un.after_command("s.json", command, now=0, state_file=state_file, collect=calls.append, echo=print)
    monkeypatch.setenv("CONTAO_AI_CLI_NO_UPDATE_CHECK", "1")
    un.after_command("s.json", "page", now=0, state_file=state_file, collect=calls.append, echo=print)
    assert calls == []


def test_an_unwritable_state_file_never_fails_the_command(tmp_path):
    blocker = tmp_path / "state"
    blocker.write_text("a file where the directory should be")
    un.after_command("s.json", "page", now=0, state_file=str(blocker / "update-check.json"),
                     collect=lambda p: STATE, echo=lambda m: None)


def test_a_slow_check_is_abandoned_at_the_deadline(tmp_path):
    """Review 2026-09-17: with the server unreachable, one command stalled for a minute."""
    import threading
    import time

    release = threading.Event()
    lines = []

    def slow(path):
        release.wait(5)
        return STATE

    started = time.monotonic()
    un.after_command("s.json", "page", now=0, state_file=str(tmp_path / "u.json"), collect=slow,
                     echo=lines.append, argv=[], deadline=0.2)
    release.set()
    assert time.monotonic() - started < 2
    assert lines == []
    saved = json.loads((tmp_path / "u.json").read_text(encoding="utf-8"))
    assert saved["sessions"]["s.json"]["lastCheckAt"] == 0


def test_a_help_lookup_never_checks(tmp_path):
    calls = []
    un.after_command("s.json", "page", now=0, state_file=str(tmp_path / "u.json"),
                     collect=calls.append, echo=print, argv=["page", "--help"])
    assert calls == []


def test_no_temp_file_is_left_behind(tmp_path):
    state_file = tmp_path / "state" / "update-check.json"
    un.after_command("s.json", "page", now=0, state_file=str(state_file),
                     collect=lambda p: STATE, echo=lambda m: None, argv=[])
    assert [p.name for p in state_file.parent.iterdir()] == ["update-check.json"]


class TestCommandFailed:
    """review 2026-09-17: the update notice used to run even for a command that
    had just failed -- a failing command has nothing to say about versions."""

    def test_no_exception_in_flight_is_not_a_failure(self):
        assert un.command_failed(None) is False

    def test_a_successful_click_exit_is_not_a_failure(self):
        from click.exceptions import Exit
        assert un.command_failed(Exit(0)) is False

    def test_a_nonzero_click_exit_is_a_failure(self):
        from click.exceptions import Exit
        assert un.command_failed(Exit(1)) is True

    def test_a_nonzero_system_exit_is_a_failure(self):
        assert un.command_failed(SystemExit(1)) is True

    def test_a_zero_system_exit_is_not_a_failure(self):
        assert un.command_failed(SystemExit(0)) is False

    def test_a_usage_error_is_a_failure(self):
        from click.exceptions import UsageError
        assert un.command_failed(UsageError("bad option")) is True


def test_a_failing_command_never_reaches_the_update_notice(monkeypatch):
    """CliRunner integration: `contao-ai-cli page` alone is a usage error."""
    from click.testing import CliRunner
    from contao_ai_cli.contao_cli import cli

    calls = []
    monkeypatch.setattr(un, "after_command", lambda *a, **k: calls.append(a))
    result = CliRunner().invoke(cli, ["page"])
    assert result.exit_code != 0
    assert calls == []
