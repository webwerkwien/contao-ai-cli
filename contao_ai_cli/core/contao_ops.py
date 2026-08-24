"""Core Contao operations: migrate, crawl, cron, filesync, maintenance."""
import json
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
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
    """Run a doctrine:query:sql and parse the table output. Returns [] on empty result."""
    result = backend.run(f'doctrine:query:sql {shlex.quote(sql)}')
    parsed = parse_table(result["stdout"])
    return parsed if isinstance(parsed, list) else []


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
