"""
SSH must never read the caller's stdin.

On 2026-08-29 a bulk run over 174 page IDs processed exactly one record and
reported success:

    while read id; do contao-ai-cli … page update "$id" --set max_teiln=4; done < ids.txt
    → "1 verarbeitet, 1 erfolgreich, 0 fehlgeschlagen", exit 0

subprocess.run() without an explicit `stdin` hands the child our own stdin, so
ssh drained the rest of the ID list on the first iteration and the loop had
nothing left to read. Nothing failed — which is what made it dangerous. It was
caught only by counting rows in the database afterwards.

Every subprocess this module starts therefore gets stdin=DEVNULL. None of these
commands has anything to read from stdin in the first place.
"""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from contao_ai_cli.utils.contao_backend import ContaoBackend


def make_backend() -> ContaoBackend:
    with patch.object(ContaoBackend, "_find_ssh", return_value="/usr/bin/ssh"), \
         patch.object(ContaoBackend, "_default_key", return_value="/home/user/.ssh/id_ed25519"):
        return ContaoBackend(
            host="example.com", user="deploy",
            contao_root="/var/www/contao",
            key_path="/home/user/.ssh/id_ed25519",
        )


def completed(stdout: str = "{}", returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


@pytest.mark.parametrize("invoke", [
    pytest.param(lambda b: b.run("contao:page:update 1 --set x=y"), id="run"),
    pytest.param(lambda b: b.run_raw("ls -la"), id="run_raw"),
])
def test_remote_commands_do_not_inherit_stdin(invoke):
    backend = make_backend()

    with patch("subprocess.run", return_value=completed()) as run:
        invoke(backend)

    assert run.call_args.kwargs.get("stdin") is subprocess.DEVNULL, (
        "Without stdin=DEVNULL, ssh eats the caller's input — see the silent "
        "single-record bulk run of 2026-08-29."
    )


def test_scp_upload_does_not_inherit_stdin():
    backend = make_backend()

    with patch("subprocess.run", return_value=completed()) as run:
        backend.scp_upload("local.txt", "/remote/local.txt")

    assert run.call_args.kwargs.get("stdin") is subprocess.DEVNULL


def test_every_subprocess_call_in_the_module_pins_stdin():
    """A new call site added without stdin= reopens the same hole silently.

    Since 2026-09-02 two call sites route the decision through
    `_stdin_kwargs()`, because passwords now go to the remote command on stdin
    and `subprocess.run()` refuses `input=` and `stdin=` together. That helper
    counts as pinning: it returns `stdin=DEVNULL` whenever no data was given, so
    the default this test was written to protect is unchanged.

    What is NOT accepted is a bare call with neither — which is exactly what the
    first version of that refactor produced, and this test caught it.
    """
    import ast
    import pathlib

    source = pathlib.Path(ContaoBackend.__module__.replace(".", "/") + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8"))

    offenders = []
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "run"
                and isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
            continue
        checked += 1

        if any(kw.arg == "stdin" for kw in node.keywords):
            continue

        # `**_stdin_kwargs(...)` — a ** unpacking carries arg=None.
        via_helper = any(
            kw.arg is None
            and isinstance(kw.value, ast.Call)
            and isinstance(kw.value.func, ast.Name)
            and kw.value.func.id == "_stdin_kwargs"
            for kw in node.keywords
        )
        if not via_helper:
            offenders.append(node.lineno)

    # A scan that matches nothing passes exactly like one that matches everything.
    assert checked >= 3, f"the scan found only {checked} subprocess.run() call sites"
    assert not offenders, f"subprocess.run() with unpinned stdin at line(s) {offenders}"


def test_the_stdin_helper_defaults_to_devnull():
    """The helper is only acceptable above because of this."""
    from contao_ai_cli.utils.contao_backend import _stdin_kwargs

    assert _stdin_kwargs(None) == {"stdin": subprocess.DEVNULL}
    assert _stdin_kwargs("secret\n") == {"input": "secret\n"}
    assert "stdin" not in _stdin_kwargs("secret\n"), "input= and stdin= together raise ValueError"
