"""Core Contao operations: migrate, crawl, cron, filesync, maintenance."""
import json
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.utils.table_parser import parse_table


def migrate(backend: ContaoBackend, dry_run: bool = False) -> dict:
    cmd = "contao:migrate --no-interaction"
    if dry_run:
        cmd += " --dry-run"
    result = backend.run(cmd)
    return {"status": "ok", "dry_run": dry_run, "output": result["stdout"]}


def install(backend: ContaoBackend) -> dict:
    result = backend.run("contao:install --no-interaction")
    return {"status": "ok", "output": result["stdout"]}


def symlinks(backend: ContaoBackend) -> dict:
    result = backend.run("contao:symlinks")
    return {"status": "ok", "output": result["stdout"]}


def filesync(backend: ContaoBackend) -> dict:
    result = backend.run("contao:filesync")
    return {"status": "ok", "output": result["stdout"]}


def cron_run(backend: ContaoBackend) -> dict:
    result = backend.run("contao:cron")
    return {"status": "ok", "output": result["stdout"]}


def cron_list(backend: ContaoBackend) -> dict:
    result = backend.run("contao:cron:list")
    return {"output": result["stdout"]}


def maintenance_enable(backend: ContaoBackend) -> dict:
    result = backend.run("contao:maintenance-mode enable")
    return {"status": "enabled", "output": result["stdout"]}


def maintenance_disable(backend: ContaoBackend) -> dict:
    result = backend.run("contao:maintenance-mode disable")
    return {"status": "disabled", "output": result["stdout"]}


def maintenance_status(backend: ContaoBackend) -> dict:
    result = backend.run("contao:maintenance-mode status")
    enabled = "enabled" in result["stdout"].lower()
    return {"enabled": enabled, "output": result["stdout"]}


def resize_images(backend: ContaoBackend) -> dict:
    result = backend.run("contao:resize-images")
    return {"status": "ok", "output": result["stdout"]}


def crawl(backend: ContaoBackend) -> dict:
    result = backend.run("contao:crawl --no-interaction")
    return {"status": "ok", "output": result["stdout"]}


def automator(backend: ContaoBackend, task: str = "") -> dict:
    """Run contao:automator tasks."""
    cmd = "contao:automator --no-interaction"
    if task:
        cmd += f" {shlex.quote(task)}"
    result = backend.run(cmd)
    return {"status": "ok", "output": result["stdout"]}


def setup(backend: ContaoBackend) -> dict:
    """Run contao:setup (post-install setup)."""
    result = backend.run("contao:setup --no-interaction")
    return {"status": "ok", "output": result["stdout"]}


# ─── Helper Functions ─────────────────────────────────────────────────────────


def run_sql_table(backend: ContaoBackend, sql: str) -> list[dict]:
    """Run a doctrine:query:sql and parse the table output. Returns [] on empty result.

    Kept for read paths that are genuinely ad hoc. Listings do NOT use this any
    more — see record_list() for why.
    """
    result = backend.run(f'doctrine:query:sql {shlex.quote(sql)}')
    parsed = parse_table(result["stdout"])
    return parsed if isinstance(parsed, list) else []


def record_list(backend: ContaoBackend, table: str, *, fields=None, filters=None,
                prefixes=None, order: str | None = None, limit=None, offset=None) -> dict:
    """
    List records through contao:record:list — the server answers in JSON.

    Replaces the hand-written SQL every listing used to carry. The difference is
    not the format:

      * the column list came from a Python f-string; now it comes from the DCA,
        and a name the table does not have is refused by name
      * every value arrived as a string — `"id": "3"`, `"sent": "1"`. Now `3`
        and `1`, and NULL is distinguishable from an empty string
      * the answer carries `count`, `total`, `limit`, `offset`, `columns`, so a
        truncated listing says so instead of looking complete

    **And the parsing itself could go wrong silently.** Symfony renders a
    table for humans; parse_table() cut it back apart by column position. That
    breaks on anything whose display width differs from its character count —
    it did on 2026-05-09, when UTF-8 umlauts shifted every column right of them
    and "Jährliche Konferenz" came back as "Jährliche Konferen", with a success
    status. A value containing a newline breaks it the same way.
    """
    cmd = f"contao:record:list {shlex.quote(table)}"

    if fields:
        cmd += f" --fields={shlex.quote(','.join(fields))}"
    for expr in (filters or []):
        cmd += f" --filter={shlex.quote(expr)}"
    for expr in (prefixes or []):
        cmd += f" --filter-prefix={shlex.quote(expr)}"
    if order:
        cmd += f" --order={shlex.quote(order)}"
    if limit is not None:
        cmd += f" --limit={int(limit)}"
    if offset:
        cmd += f" --offset={int(offset)}"

    return run_json_or_raw(backend, cmd)


def run_json_or_raw(backend: ContaoBackend, cmd: str) -> dict:
    """Run a Contao console command and parse JSON output, falling back to raw string.

    Caller is responsible for quoting any user-supplied arguments in `cmd`
    (e.g. via shlex.quote).
    """
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def run_update(backend, command: str, record_id: int, fields: dict) -> dict:
    """
    Run an <entity>:update command for one record.

    The core bundle takes the ID as an argument and every changed field as a
    repeated --set, which is what build_set_args produces.
    """
    cmd = f"{command} {int(record_id)} {build_set_args(fields)} --no-interaction"
    return run_json_or_raw(backend, " ".join(cmd.split()))


def run_bulk_update(backend, command: str, ids: list[int], fields: dict) -> dict:
    """
    Run an <entity>:update command for many records over one connection.

    Needs core-bundle >= v0.2.15 for `--ids`. The server loops; each record still
    gets its own version and its own system-log entry, so the audit trail is
    identical to running the command once per ID. Only the connection is shared —
    and that is where the time went: of the 1.4 s a single record cost on
    2026-08-29, 0.67 s was establishing the SSH connection.

    Returns the summary payload: total, succeeded, failed, ids, errors.
    """
    id_list = ",".join(str(int(i)) for i in ids)
    cmd = " ".join(f"{command} --ids={id_list} {build_set_args(fields)} --no-interaction".split())

    # check=False: a partial run exits non-zero on purpose, so a shell loop
    # notices — but the JSON summary is what names the failed records, and
    # letting run() raise discarded it.
    result = backend.run(cmd, check=False)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        # No JSON at all means the command never ran; that is a real failure.
        if result["returncode"] != 0:
            raise ContaoBackendError(
                f"Bulk update failed (exit {result['returncode']}): "
                f"{result['stderr'][:500] or result['stdout'][:500]}"
            ) from None
        return {"raw": result["stdout"]}


def run_delete(backend, command: str, record_id: int) -> dict:
    """
    Run an <entity>:delete command for one record.

    Since core-bundle v0.2.8 this cascades to child records and writes a single
    tl_undo entry covering all of them, so a deletion stays recoverable from the
    back end's "Restore" module.
    """
    return run_json_or_raw(backend, f"{command} {int(record_id)} --no-interaction")


def run_publish(backend, command: str, record_id: int, published: bool) -> dict:
    """Run a :publish command, whose second argument is publish|unpublish."""
    action = "publish" if published else "unpublish"
    return run_json_or_raw(backend, f"{command} {int(record_id)} {action} --no-interaction")


def build_set_args(fields: dict[str, str]) -> str:
    """Build --set key=value argument string for Contao console commands."""
    if not fields:
        return ""
    return " ".join(f"--set {shlex.quote(f'{k}={v}')}" for k, v in fields.items())
