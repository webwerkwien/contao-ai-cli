"""The report is generated when something is already broken.

That is the whole difficulty: every assumption about the process being healthy
is the one that just failed. So these tests ask what can get *into* a report
rather than whether it renders, and the field list below fails when a field is
added -- a test that only checks the fields it knows about approves of every new
one, which is how something leaks past a green suite.
"""
import re

import pytest

from contao_ai_cli.utils import error_report


SECRET = "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789"

# Every label the report may carry. Adding one has to be a decision, not a
# side effect -- hence a list to update rather than an assertion to widen.
ALLOWED_LABELS = {
    "zeitpunkt",
    "komponente",
    "versionen.cli",
    "umgebung.python",
    "umgebung.os",
    "ausnahme.klasse",
    "ausnahme.datei",
    "ausnahme.zeile",
    "befehl",
    "status",
}


def raise_it(exc):
    """Raise and catch, so the exception carries a real traceback."""
    try:
        raise exc
    except type(exc) as caught:
        return caught


def labels_of(report: str) -> set:
    return set(re.findall(r"^\| ([a-z.]+) \|", report, re.MULTILINE))


def test_report_carries_only_allow_listed_labels():
    report = error_report.build(
        raise_it(RuntimeError("kaputt")),
        {"befehl": "news update", "status": 500},
    )

    unexpected = labels_of(report) - ALLOWED_LABELS
    assert not unexpected, (
        "new field(s) in the report: %s -- decide whether they may be disclosed, "
        "then add them here" % sorted(unexpected)
    )


def test_the_notice_is_always_present():
    report = error_report.build(raise_it(RuntimeError("kaputt")))
    assert error_report.NOTICE in report


def test_a_pattern_matched_secret_is_masked():
    report = error_report.build(raise_it(RuntimeError("Anfrage mit %s" % SECRET)))

    assert SECRET not in report
    assert "sk-***" in report


def test_a_literal_secret_is_struck_without_a_matching_pattern():
    """The half that actually works: we hold the token, so we need not guess."""
    opaque = "Ff8kQz2mWx7bVn4t"
    report = error_report.build(
        raise_it(RuntimeError("Token %s abgelehnt" % opaque)),
        known_secrets=(opaque,),
    )

    assert opaque not in report


def test_paths_do_not_name_the_user():
    report = error_report.build(raise_it(RuntimeError("kaputt")))

    assert "C:/Users" not in report
    assert "C:\\Users" not in report
    assert "/home/" not in report
    # Our own code stays identifiable.
    assert "contao_ai_cli/tests/test_error_report.py" in report


def test_foreign_frames_are_collapsed():
    """A stack trace is mostly plumbing; the report keeps our part of it.

    The callback has to travel through *Python* library code to leave a frame.
    The first version of this test used `sorted(key=...)`, which is implemented
    in C and leaves none -- so every frame was ours and the assertion failed on
    correct code. `json.loads` decodes in Python and does leave one.
    """
    import json

    def explode(_):
        raise RuntimeError("kaputt")

    try:
        json.loads('{"a": 1}', object_hook=explode)
    except RuntimeError as exc:
        report = error_report.build(exc)

    assert "ausserhalb von contao-ai" in report
    assert "json/decoder.py" not in report
    assert "explode() in contao_ai_cli/tests/test_error_report.py" in report


def test_the_report_survives_a_cp1252_stdout():
    """Redirected output, cron and agent harnesses get the locale encoding.

    A character outside cp1252 raises UnicodeEncodeError mid-line -- and a
    report that cannot be printed at the moment of failure is worse than none,
    because it replaces one error with a second, more confusing one.
    """
    report = error_report.build(
        raise_it(RuntimeError("Umlaute: aeoeue und ein Gedankenstrich -")),
        {"befehl": "news update"},
    )

    report.encode("cp1252")  # raises if anything is outside it


class _BridgeLike(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


@pytest.mark.parametrize(
    "exc,expected",
    [
        (_BridgeLike("kaputt", 500), True),
        (_BridgeLike("kaputt", 503), True),
        (_BridgeLike("Token ungueltig", 401), False),
        (_BridgeLike("nicht gefunden", 404), False),
        (_BridgeLike("kaputt", None), True),
        (_BridgeLike("kaputt", "unsinn"), True),
        (RuntimeError("kaputt"), True),
    ],
)
def test_only_defects_are_reportable(exc, expected):
    """The same 500/422 line the bundles draw: 5xx broke, 4xx is an answer."""
    assert error_report.is_reportable(exc) is expected


def test_emit_writes_to_stderr_not_stdout(capsys):
    """stdout may be carrying JSON a caller is parsing."""
    error_report.emit(raise_it(RuntimeError("kaputt")))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Fehlerbericht contao-ai" in captured.err


def test_the_console_script_points_at_a_function_that_exists():
    """The entry point moved from `cli` to `main` in v0.16.0.

    Nothing else would notice if it had not: every test calls the command
    functions directly, and a broken `console_scripts` target only shows up
    after `pipx install`, on someone else's machine. So the declaration in
    setup.py is read and resolved here.
    """
    import importlib
    import pathlib

    setup_py = (pathlib.Path(__file__).parents[2] / "setup.py").read_text(encoding="utf-8")

    match = re.search(r"contao-ai-cli=([\w.]+):(\w+)", setup_py)
    assert match, "console_scripts entry for contao-ai-cli not found in setup.py"

    module = importlib.import_module(match.group(1))
    assert callable(getattr(module, match.group(2), None)), (
        "setup.py points at %s:%s, which is not callable" % match.groups()
    )


def test_main_attaches_a_report_to_an_unexpected_failure(monkeypatch, capsys):
    from contao_ai_cli import contao_cli

    def boom(*args, **kwargs):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(contao_cli, "cli", boom)

    with pytest.raises(SystemExit) as exit_info:
        contao_cli.main()

    assert exit_info.value.code == 1

    err = capsys.readouterr().err
    assert "Error: unerwartet" in err
    assert "Fehlerbericht contao-ai" in err


def test_main_stays_quiet_for_a_bridge_answer(monkeypatch, capsys):
    """A 404 from the bridge is a statement about the request, not a defect."""
    from contao_ai_cli import contao_cli

    def boom(*args, **kwargs):
        raise _BridgeLike("Route nicht gefunden", 404)

    monkeypatch.setattr(contao_cli, "cli", boom)

    with pytest.raises(SystemExit):
        contao_cli.main()

    err = capsys.readouterr().err
    assert "Error: Route nicht gefunden" in err
    assert "Fehlerbericht contao-ai" not in err


def test_main_does_not_report_a_user_interrupt(monkeypatch, capsys):
    """Ctrl+C is a decision, and 130 is what a shell expects for it."""
    from contao_ai_cli import contao_cli

    def boom(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(contao_cli, "cli", boom)

    with pytest.raises(SystemExit) as exit_info:
        contao_cli.main()

    assert exit_info.value.code == 130
    assert "Fehlerbericht" not in capsys.readouterr().err


def test_argument_values_are_never_taken_from_the_context():
    """`build()` reads two named keys; anything else a caller passes is ignored.

    A caller under pressure hands over what it has -- including the parsed
    arguments. Reading only named keys means that mistake costs nothing.
    """
    report = error_report.build(
        raise_it(RuntimeError("kaputt")),
        {"befehl": "news update", "headline": SECRET, "arguments": {"text": SECRET}},
    )

    assert SECRET not in report
