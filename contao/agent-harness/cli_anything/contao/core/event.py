"""Contao calendar event management (tl_calendar_events, tl_calendar)."""
import json
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def calendar_list(backend: ContaoBackend) -> list:
    """List all calendars (tl_calendar)."""
    sql = "SELECT id, title FROM tl_calendar ORDER BY title"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def event_list(backend: ContaoBackend, calendar_id: int = None) -> list:
    """List calendar events. Optionally filter by calendar ID (pid)."""
    where = f"WHERE pid = {calendar_id}" if calendar_id is not None else ""
    sql = (
        f"SELECT id, pid, title, alias, published, startDate, endDate "
        f"FROM tl_calendar_events {where} ORDER BY startDate DESC"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def event_create(backend: ContaoBackend, title: str, pid: int,
                 start_date: str = None, end_date: str = None,
                 fields: dict = None) -> dict:
    """Create a calendar event via contao-cli-bridge."""
    cmd = f"contao:event:create --title={shlex.quote(title)} --pid={pid} --no-interaction"
    if start_date:
        cmd += f" --startDate={shlex.quote(start_date)}"
    if end_date:
        cmd += f" --endDate={shlex.quote(end_date)}"
    if fields:
        cmd += " " + " ".join(f"--set {shlex.quote(f'{k}={v}')}" for k, v in fields.items())
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"status": "ok", "output": result["stdout"]}
