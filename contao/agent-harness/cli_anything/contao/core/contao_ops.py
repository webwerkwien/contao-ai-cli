"""Core Contao operations: migrate, crawl, cron, filesync, maintenance."""
import json
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


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
    """Run a Contao console command and parse JSON output, falling back to raw string."""
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def build_set_args(fields: dict[str, str]) -> str:
    """Build --set key=value argument string for Contao console commands."""
    if not fields:
        return ""
    return " ".join(f"--set {shlex.quote(f'{k}={v}')}" for k, v in fields.items())
