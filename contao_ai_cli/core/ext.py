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
import json
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

    # Commands the server reports as out of reach — everything outside the
    # `contao:` namespace. Named rather than filtered, and that is a correction:
    # leaving them out made this command answer "available: 0" on an
    # installation with 87 commands it could not reach, through the very command
    # built to report what it cannot reach. Reported by the ww-buchung session,
    # whose own `ww:gutschein:import` was invisible here.
    #
    # `ext run` still refuses them — the boundary is on running, not on naming.
    out_of_reach = [c for c in answer["commands"] if c.get("reachable") is False]
    reachable    = [c for c in answer["commands"] if c.get("reachable") is not False]

    unwrapped = [c for c in reachable if c.get("name") not in wrapped]

    infrastructure = [c for c in unwrapped if c.get("name") in _INFRASTRUCTURE]
    if not include_infrastructure:
        unwrapped = [c for c in unwrapped if c.get("name") not in _INFRASTRUCTURE]
    else:
        for entry in infrastructure:
            entry["infrastructure"] = _INFRASTRUCTURE[entry["name"]]

    result = {
        "status": "ok",
        "total": answer.get("count", len(answer["commands"])),
        "wrapped": len(reachable) - len(unwrapped) - (0 if include_infrastructure else len(infrastructure)),
        "infrastructure": len(infrastructure),
        "available": len(unwrapped),
        "commands": unwrapped,
    }

    if out_of_reach:
        result["out_of_reach"] = len(out_of_reach)
        result["out_of_reach_note"] = (
            "Outside the contao: namespace, so ext run will not start them — doctrine:query:sql "
            "above all. Counted here because a command this CLI cannot reach is exactly what this "
            "listing is for. A command becomes reachable either by living under contao: or by "
            "declaring an #[AiContract] — a plugin does not have to rename itself, and should not: "
            "a prefix of its own is the convention, and contao: is someone else's property."
        )
        if include_infrastructure:
            result["out_of_reach_commands"] = out_of_reach

    return result


def ext_describe(backend: ContaoBackend, name: str) -> dict:
    """Arguments, options and help for one command, straight from the server."""
    return run_json_or_raw(
        backend, f"contao:ai:commands --name={shlex.quote(name)}"
    )


def ext_run(backend: ContaoBackend, command_line: str, operator: str = "") -> dict:
    """
    Run an unwrapped command through contao:ai:run, inside an envelope.

    The server writes the log entry before it starts the target, so a command
    that crashes still leaves the record that it was started. The warning to the
    caller is the CLI's half of the same decision — see cli_ext.py.

    ## Why the answer is wrapped instead of passed through

    Until 2026-09-01 this returned the target's stdout as its own result. A
    throwaway plugin on c5 answered:

        { "status": "ok", "echo": "HALLO" }

    and the CLI printed exactly that. The `status: ok` is the *plugin's* word,
    standing where every wrapped command puts the CLI's — two different claims
    under one name, which is the failure this whole group was built against.

    For a wrapped command the CLI knows the shape, because the core bundle
    produces it. For an unwrapped one the shape is unknown by definition: a
    plugin may answer `status: ok` and have done nothing, or exit non-zero while
    its JSON still reads ok. `AiRunCommand` deliberately does not normalise it —
    *"this command promises to run it and to have said so, not to normalise what
    it answers"* — so the separation belongs on this side.

    `status` here is this CLI's verdict on the run and is derived from the exit
    code alone. Everything the foreign command said sits under `output`,
    untouched, and nothing it says can reach the top level.
    """
    cmd = f"contao:ai:run --command-line={shlex.quote(command_line)}"
    if operator:
        cmd += f" --operator={shlex.quote(operator)}"

    # check=False: a non-zero exit is the most useful thing this function can
    # report about a command it does not understand, and raising would throw it
    # away along with whatever the target managed to say first.
    result = backend.run(cmd, check=False)

    try:
        output = json.loads(result["stdout"])
    except (json.JSONDecodeError, TypeError):
        output = result["stdout"]

    envelope = {
        "status": "ok" if 0 == result["returncode"] else "error",
        "command": command_line,
        # Stated rather than implied. A reader that sees this field knows none
        # of the wrapped commands' guarantees applied to what is under `output`.
        "wrapped": False,
        "exit_code": result["returncode"],
        # Not `output`: `_output()` treats a field of that name as raw
        # passthrough and prints it *instead of* the surrounding dict, so the
        # envelope would vanish in exactly the mode a human reads. Around 40
        # commands rely on that convention for their stdout, so the name gives
        # way here rather than the convention there.
        "command_output": output,
    }

    # Only on a failed run, and the rule is stated rather than left to be
    # noticed: the absence of this field means the command succeeded, never
    # that stderr was clean.
    #
    # Every other command in this CLI ignores stderr completely, so carrying it
    # is new here — and c5 shows why it cannot be carried unconditionally: PHP
    # emits ionCube and imagick startup warnings on every single call, which
    # would put several lines of unrelated noise in front of an agent on every
    # successful run and teach it to skip the field. When the run fails, stderr
    # is often the only place the reason exists — a plugin that dies before the
    # error boundary catches it leaves nothing on stdout at all.
    if 0 != result["returncode"] and result.get("stderr"):
        envelope["stderr"] = result["stderr"]

    # `check=False` above means backend.run() never raises here, and the hint
    # about an outdated bundle rides on that raise — so ext run was silent
    # about the one thing it is best placed to explain. Measured by the
    # ww-buchung session (2026-09-01), which reached for `ext run` and
    # `ext describe` to ask about a command it did not have, and got no version
    # context at all.
    if 0 != result["returncode"]:
        hint = backend.undefined_command_hint(result["stdout"], result.get("stderr", ""))
        if hint:
            envelope["hint"] = hint.strip()

    return envelope


def refuse_unreachable(described: dict | None) -> str | None:
    """
    Refuse a command the server says it will not run, before warning about it.

    The ordering is the point: the warning ends with *"the invocation is
    recorded in the system log"*, and for a command the server refuses, nothing
    is recorded. Printing it first stated something untrue about a run that was
    not going to happen.

    ## Why this reads the server's answer instead of repeating its rule

    It used to be a local copy of the rule — "starts with `contao:`" — and this
    docstring justified the duplication on two grounds: that the rule was
    *trivially stable*, and that a copy could only ever refuse earlier, never
    grant more.

    Both failed the same afternoon. The rule stopped being "starts with
    contao:" the moment a declared #[AiContract] also opened the door, and the
    copy then refused a command the server was willing to run — granting less,
    which is the same drift wearing the other face. The lesson is not that the
    copy was written carelessly: a duplicated rule is a bet on the original
    never changing.

    `ext run` already asks the server to describe the command, to learn what it
    declared. That same answer carries `reachable`, so the ordering is kept for
    free and there is nothing left to drift.

    Returns the refusal, or None.
    """
    if not isinstance(described, dict) or described.get("reachable") is not False:
        return None

    return described.get("reachable_note") or "The server will not run this command."



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


def contract_warning(contract: dict | None) -> str:
    """
    What a command declared about itself, for the warning before it runs.

    The blanket warning ends with *"no promise that it writes a version, an
    undo entry or a log line of its own"* — correct for a silent plugin, and
    untrue the moment one declares `trace` and `traceWhen`. Saying "nothing is
    promised" where something was is the same failure as the rest of this week:
    a sentence that is easy to read and no longer matches what it describes.

    The replacement must not overcorrect either. A declaration is the command's
    own word and this CLI enforces none of it, so the text says what was
    declared **and** that nobody checked it. Dropping either half misleads in
    one direction or the other.

    Returns "" when there is nothing to say — including for a declaration that
    failed validation, which promises nothing.
    """
    if not contract or not isinstance(contract, dict):
        return ""

    checked   = contract.get("checked") or {}
    statement = contract.get("checked_with_statement") or {}
    declared  = contract.get("declared") or {}

    if not (checked or statement or declared):
        return ""

    lines = [
        "",
        "It declares the following about itself. Nothing here checks any of it — the",
        "declaration is the command's own word.",
    ]

    if (tables := checked.get("tables")):
        line = f"  tables        {', '.join(tables)}"
        if (missing := checked.get("tables_without_dca")):
            # A named table with no DCA is a typo or a missing extension, and
            # both matter more before the run than after.
            line += f"   (no DCA here: {', '.join(missing)})"
        lines.append(line)

    if "writes" in statement:
        lines.append(f"  writes        {'yes' if statement['writes'] else 'no'}")

    if (trace := statement.get("trace")):
        when = statement.get("trace_when")
        # The period is read from the installation, not declared — and it is
        # the difference between a trail that outlives the question and one
        # that does not.
        periods = ", ".join(
            f"{t} kept {statement.get('retention', {}).get(t, {}).get('days', '?')} days"
            for t in trace
        )
        # Two values, two sentences. A single template read "written on-success
        # the run" — the kind of thing that survives review because the field is
        # correct and only the sentence around it is not.
        timing = {
            "before":     ", written before the run",
            "on-success": ", written only if the run succeeds",
        }.get(when, "")
        lines.append(f"  trail         {periods}{timing}")

    if (shape := statement.get("answer_shape")):
        lines.append(f"  answers with  {', '.join(shape)}")

    if (unsuitable := checked.get("generic_path_unsuitable")):
        for table, reason in unsuitable.items():
            lines.append(f"  hands off     {table} — {reason}")

    if "repeatable" in declared:
        lines.append(f"  repeatable    {'yes' if declared['repeatable'] else 'no'}")

    if (irreversible := declared.get("irreversible_outside_database")):
        # Last and on its own line, because it is the one a caller has to stop
        # at. A database write has tl_undo; this has nothing.
        lines += [
            "",
            f"  IRREVERSIBLE  {irreversible}",
            "                This cannot be undone by anything in this CLI.",
        ]

    return "\n".join(lines)
