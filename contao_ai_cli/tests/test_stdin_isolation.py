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
    """A new call site added without stdin= reopens the same hole silently."""
    import ast
    import pathlib

    source = pathlib.Path(ContaoBackend.__module__.replace(".", "/") + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8"))

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "run"
                and isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
            continue
        if not any(kw.arg == "stdin" for kw in node.keywords):
            offenders.append(node.lineno)

    assert not offenders, f"subprocess.run() without stdin= at line(s) {offenders}"
