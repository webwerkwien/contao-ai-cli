"""
What this installation offers beyond the commands the CLI wraps.

The CLI wraps a curated set of console commands, one Python function each. An
extension that ships its own `contao:*` command registers it with Symfony and is
then invisible from here: it exists on the server, and nothing in the CLI — or
in an agent reading `--help` — can learn that it does.

`ext list` answers that. `ext run` executes one, with a warning to the caller
and an entry in the system log, because a foreign command carries none of the
guarantees the wrapped ones do.
"""
import ast
import pathlib
import re
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import run_json_or_raw

#: Where the scan below looks. The package, not the tests: a command named only
#: in a test fixture is not reachable from the command line.
_PACKAGE = pathlib.Path(__file__).parent.parent

_COMMAND_PATTERN = re.compile(r"contao:[a-z0-9:_-]+")

#: The two commands this module itself drives. Counted as wrapped, because they
#: are: `ext list` and `ext run` are their wrappers. Leaving them out of the set
#: made them show up as things the CLI cannot reach — through the very command
#: that reaches them.
_OWN = {"contao:ai:commands", "contao:ai:run"}

#: Contao's own plumbing: commands that exist on every installation and that
#: nobody drives from here. Set aside rather than hidden — `ext list` reports
#: how many, and `--all` shows them.
#:
#: The judgement is the CLI's, so it belongs here and not on the server, and it
#: is stated with a reason each. A silent filter would make `ext list` quietly
#: incomplete, which is the failure this whole group exists to fix.
_INFRASTRUCTURE = {
    "contao:dump-twig-ide-file":
        "writes an IDE lookup file — local development, not remote site management",
    "contao:install-web-dir":
        "restores the manager skeleton files; part of installing, run by the Contao Manager",
    "contao:supervise-workers":
        "a long-running process supervisor, started by the system rather than by a caller",
}


def _command_names_in_code(source: str) -> set[str]:
    """
    Command names in string literals that are not docstrings.

    Over the AST rather than the raw text, and the reason is a bug this made
    within minutes of being written: the `ext run` help text carries the example
    `contao:some-plugin:sync`, a plain-text scan counted it as wrapped, and the
    command it was meant to illustrate became invisible to `ext list`.

    Any command named in prose would have done the same. Documentation is where
    unwrapped commands get *mentioned*, so prose is precisely the wrong evidence
    for "this one is handled". Comments never reach the AST; docstrings are
    skipped explicitly.
    """
    tree = ast.parse(source)

    docstrings = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            docstrings.add(id(body[0].value))

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            names |= set(_COMMAND_PATTERN.findall(node.value))

    return names


def wrapped_commands() -> set[str]:
    """
    The `contao:*` commands this CLI actually sends.

    Derived rather than listed. A hand-maintained set of 130 names would be a
    second copy of something the code already states, and the copy is the one
    that goes stale — this project has watched that happen to a version constant
    and to two exclude patterns.
    """
    found: set[str] = set()

    for path in _PACKAGE.rglob("*.py"):
        if "tests" in path.parts:
            continue
        try:
            found |= _command_names_in_code(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue

    # _INFRASTRUCTURE is subtracted, not left to chance: its keys are string
    # literals in this very module, so the scan finds them and would count them
    # as wrapped — naming a command in order to set it aside would mark it as
    # handled. Third time today that mentioning a command made it count as
    # covered; the first was the help-text example, the second a docstring.
    return ({name for name in found if not name.endswith(":")} - set(_INFRASTRUCTURE)) | _OWN


def ext_list(backend: ContaoBackend, include_infrastructure: bool = False) -> dict:
    """
    The commands this installation has and the CLI does not wrap.

    The server answers what exists; the subtraction happens here, because what
    the CLI wraps is the CLI's own business and a copy of it on the server would
    drift from the original.

    Contao's own plumbing is set aside by default and counted in
    `infrastructure`, so the number is visible even when the entries are not.
    """
    answer = run_json_or_raw(backend, "contao:ai:commands")

    if not isinstance(answer, dict) or "commands" not in answer:
        return answer

    wrapped = wrapped_commands()
    unwrapped = [c for c in answer["commands"] if c.get("name") not in wrapped]

    infrastructure = [c for c in unwrapped if c.get("name") in _INFRASTRUCTURE]
    if not include_infrastructure:
        unwrapped = [c for c in unwrapped if c.get("name") not in _INFRASTRUCTURE]
    else:
        for entry in infrastructure:
            entry["infrastructure"] = _INFRASTRUCTURE[entry["name"]]

    return {
        "status": "ok",
        "total": answer.get("count", len(answer["commands"])),
        "wrapped": len(answer["commands"]) - len(unwrapped) - (0 if include_infrastructure else len(infrastructure)),
        "infrastructure": len(infrastructure),
        "available": len(unwrapped),
        "commands": unwrapped,
    }


def ext_describe(backend: ContaoBackend, name: str) -> dict:
    """Arguments, options and help for one command, straight from the server."""
    return run_json_or_raw(
        backend, f"contao:ai:commands --name={shlex.quote(name)}"
    )


def ext_run(backend: ContaoBackend, command_line: str, operator: str = "") -> dict:
    """
    Run an unwrapped command through contao:ai:run.

    The server writes the log entry before it starts the target, so a command
    that crashes still leaves the record that it was started. The warning to the
    caller is the CLI's half of the same decision — see cli_ext.py.
    """
    cmd = f"contao:ai:run --command-line={shlex.quote(command_line)}"
    if operator:
        cmd += f" --operator={shlex.quote(operator)}"
    return run_json_or_raw(backend, cmd)


def refuse_outside_contao(command_line: str) -> str | None:
    """
    Refuse a command outside the `contao:` namespace, before warning about it.

    The server refuses these too — `AiRunGuard` is the authority and stays that
    way. This is not a second boundary but a check of order: without it the
    warning printed first, and the warning says *"the invocation is recorded in
    the system log"*. For a command the server then refuses, nothing is
    recorded, so the CLI was stating something untrue about what had just
    happened.

    Duplicating a rule is normally the wrong move here, and this one is only
    defensible because it is trivially stable ("starts with contao:") and
    because the copy cannot grant anything the server would refuse — it can
    only refuse earlier.

    Returns the refusal, or None.
    """
    name = command_line.strip().split(" ", 1)[0]

    if name.startswith("contao:"):
        return None

    return (
        f'"{name}" is outside the contao: namespace and ext run will not reach it.\n'
        "doctrine:query:sql above all: a generic runner that reaches raw SQL would put every\n"
        "DCA rule, version and log entry this bundle writes back on the honour system.\n"
        "Not a security boundary — whoever runs this has shell access — but a bound on what\n"
        "the tool does on its own. Use the dedicated command, or a shell."
    )


def refuse_wrapped(command_line: str) -> str | None:
    """
    Why `ext run` will not touch a command the CLI already wraps.

    Not a safety rule — the wrapped command would run perfectly well. It is
    about there being one answer to "how do I do X". The wrapper applies
    conversions, checks and output shaping that the raw command does not, so the
    two would return different things under the same name, and which one a
    caller got would depend on how they happened to phrase the request.

    Returns the refusal, or None when the command is genuinely unwrapped.
    """
    name = command_line.strip().split(" ", 1)[0]

    if name not in wrapped_commands():
        return None

    return (
        f'"{name}" is wrapped by this CLI — use the dedicated command instead of ext run.\n'
        "The wrapper is not a thin passthrough: it converts fields, checks them against the\n"
        "DCA and shapes the answer. Running the bare command here would answer differently\n"
        "under the same name, and which one you got would depend on how you asked."
    )
