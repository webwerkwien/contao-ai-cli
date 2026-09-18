"""
A one-line update notice when a new working block starts.

Decided 2026-09-17: checked on the first command after a pause of more than 12 hours
(a new block - the moment to hear about updates), and at least every 24 hours so
continuous use (cron, monitoring) is still checked. The CLI remembers, not the agent:
a new conversation knows nothing about yesterday, the file system does.

The state lives in a subdirectory because `session-list` reads every *.json directly
in ~/.contao-ai-cli as a session. Output goes to stderr only; no answer changes.
The hook runs when the command's context closes: after its output when it succeeds,
but before click prints the error of a failing command.
"""
import json
import os
import sys
import threading
import time

from contao_ai_cli.core import session as session_mod

STATE_FILE = os.path.join(session_mod.DEFAULT_SESSION_DIR, "state", "update-check.json")
PAUSE = 12 * 3600
MAX_AGE = 24 * 3600
SKIPPED = {"health", "self-update", "bundle", "connect", "repl",
          # Purely local: neither reads nor writes anything remote, so there is
          # nothing here that an update notice adds (review 2026-09-17).
          "session-list", "session-delete", "guide", None}
OPT_OUT = "CONTAO_AI_CLI_NO_UPDATE_CHECK"
# The check reads GitHub, Packagist and the server over SSH. Each call has its own
# timeout, but they add up: with the server unreachable one ordinary command stalled
# for up to a minute (review 2026-09-17). Whatever is not answered in time is skipped;
# the next trigger tries again.
DEADLINE = 10


def is_due(entry: dict, now: float) -> bool:
    last_check = entry.get("lastCheckAt")
    if last_check is None or now - last_check >= MAX_AGE:
        return True
    last_command = entry.get("lastCommandAt")
    return last_command is not None and now - last_command > PAUSE


def format_notice(state: dict) -> str | None:
    parts = []
    cli = state.get("cli", {})
    if cli.get("up_to_date") is False and cli.get("latest"):
        parts.append(f"CLI {cli.get('installed')} -> {cli['latest']}")
    for key, label in (("core", "core-bundle"), ("backend", "backend-bundle")):
        info = state.get(key, {})
        if info.get("update_available") and info.get("installed") and not str(info["installed"]).startswith("dev-"):
            parts.append(f"{label} {info['installed']} -> {info.get('latest')}")
    if not parts:
        return None
    return "Updates: " + ", ".join(parts) + " - contao-ai-cli health"


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict, path: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Per process: two commands running at once must not write into one temp file
        # (review 2026-09-17 - one of them lost its timestamps).
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        pass  # never fail the command over its notice


def command_failed(exc) -> bool:
    """
    Whether the command this hook is closing for actually failed.

    `exc` is `sys.exc_info()[1]` at the point the click context is closing --
    still the command's own exception at that point, before click's `main()`
    turns it into the process exit code. `None` means a plain return.
    click.exceptions.Exit and SystemExit both carry a code that can be zero
    (`ctx.exit()` and a deliberate `raise SystemExit(0)` are successful exits),
    so those two are read by their code rather than by being an exception at
    all. Anything else that reached here -- a UsageError, a real exception --
    is a failure (review 2026-09-17: the notice used to run regardless, and a
    failing command has nothing to say about whether the CLI or the bundles
    are current).
    """
    if exc is None:
        return False
    if isinstance(exc, SystemExit):
        return exc.code not in (0, None)
    import click.exceptions
    if isinstance(exc, click.exceptions.Exit):
        return exc.exit_code != 0
    return True


def _collect_within(collect, session_path, deadline: float) -> dict | None:
    """The state, or None when it failed or took longer than the deadline."""
    result: dict = {}

    def run():
        try:
            result["state"] = collect(session_path)
        except Exception:  # noqa: BLE001 - offline or unreachable counts as checked
            pass

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(deadline)
    return result.get("state")


def after_command(session_path, command, now=None, state_file=STATE_FILE, collect=None, echo=None,
                  argv=None, deadline=DEADLINE) -> None:
    if command in SKIPPED or os.environ.get(OPT_OUT):
        return
    # `page --help` reaches this hook with command "page"; a help lookup stays instant.
    if "--help" in (sys.argv[1:] if argv is None else argv):
        return
    now = time.time() if now is None else now
    data = _load(state_file)
    sessions = data.setdefault("sessions", {})
    entry = sessions.setdefault(str(session_path), {})
    due = is_due(entry, now)
    entry["lastCommandAt"] = now
    if due:
        entry["lastCheckAt"] = now
    # Saved before the check, so an interrupted or slow check still counts.
    _save(data, state_file)

    if not due:
        return
    if collect is None:
        from contao_ai_cli.core.status import collect_status as collect
    state = _collect_within(collect, session_path, deadline)
    message = format_notice(state) if state else None
    if message:
        if echo is None:
            import click
            echo = lambda m: click.echo(m, err=True)  # noqa: E731
        echo(message)
