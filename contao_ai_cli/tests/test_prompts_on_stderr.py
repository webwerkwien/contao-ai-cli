"""Every confirmation question goes to stderr, so stdout stays free for the answer.

v0.18.0 said "Prompts go to stderr", and it held for ``ask_yes_no()`` only. The six
``click.confirm()`` calls in ``cli_connect.py`` still printed on stdout — found in the
review of 2026-09-16. They are interactive flows without ``--json``, so nothing broke,
but the release note promised more than the code did.

2026-09-17: the agent-onboarding rework deleted the whole ``connect`` wizard those
six calls lived in - ``connect`` no longer asks anything. What is left is the hidden
``click.prompt()`` for the bridge token in ``helpers.resolve_token()``, so the minimum
below tracks that, not the historical six. Fewer prompts is the point of the change;
what still has to hold is that every prompt that does exist writes to stderr.

Checked on the syntax tree rather than by running the flows: each needs SSH and a
server. A call without ``err=True`` fails here by file and line.
"""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def _confirm_calls():
    for path in PACKAGE.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("confirm", "prompt")
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "click"):
                yield path, node


def test_the_scan_finds_the_confirm_calls():
    # A sanity check that the scan itself still works, not a target to defend -
    # see the module docstring for why this dropped from 6.
    assert len(list(_confirm_calls())) >= 1


def test_every_click_prompt_writes_to_stderr():
    missing = []
    for path, node in _confirm_calls():
        err = next((kw for kw in node.keywords if kw.arg == "err"), None)
        if err is None or not (isinstance(err.value, ast.Constant) and err.value.value is True):
            missing.append(f"{path.name}:{node.lineno}")

    assert missing == [], "click prompts on stdout: " + ", ".join(missing)
