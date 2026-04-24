"""Contao calendar event management (tl_calendar_events, tl_calendar)."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def calendar_list(backend: ContaoBackend) -> list:
    """List all calendars (tl_calendar)."""
    sql = "SELECT id, title FROM tl_calendar ORDER BY title"
    return run_sql_table(backend, sql)


def event_list(backend: ContaoBackend, calendar_id: int | None = None) -> list:
    """List calendar events. Optionally filter by calendar ID (pid)."""
    where = f"WHERE pid = {int(calendar_id)}" if calendar_id is not None else ""
    sql = (
        f"SELECT id, pid, title, alias, published, startDate, endDate "
        f"FROM tl_calendar_events {where} ORDER BY startDate DESC"
    )
    return run_sql_table(backend, sql)


def event_read(backend: ContaoBackend, event_id: int) -> dict:
    """Read all fields of a tl_calendar_events record."""
    return run_json_or_raw(backend, f"contao:event:read {event_id}")


def event_create(backend: ContaoBackend, title: str, pid: int,
                 start_date: str | None = None, end_date: str | None = None,
                 fields: dict | None = None) -> dict:
    """Create a calendar event via contao-cli-bridge."""
    cmd = f"contao:event:create --title={shlex.quote(title)} --pid={pid} --no-interaction"
    if start_date:
        cmd += f" --startDate={shlex.quote(start_date)}"
    if end_date:
        cmd += f" --endDate={shlex.quote(end_date)}"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)
