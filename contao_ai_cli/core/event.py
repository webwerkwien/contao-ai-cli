"""Contao calendar event management (tl_calendar_events, tl_calendar)."""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    run_sql_table, run_json_or_raw, build_set_args, run_update, run_delete,
)


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
    """Create a calendar event via contao-ai-core-bundle."""
    cmd = f"contao:event:create --title={shlex.quote(title)} --pid={pid} --no-interaction"
    if start_date:
        cmd += f" --startDate={shlex.quote(start_date)}"
    if end_date:
        cmd += f" --endDate={shlex.quote(end_date)}"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def event_update(backend: ContaoBackend, event_id: int, fields: dict) -> dict:
    """Update event fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:event:update", event_id, fields)


def event_delete(backend: ContaoBackend, event_id: int) -> dict:
    """
    Delete an event via contao-ai-core-bundle.
    Cascades to the event's content elements.
    Recoverable from the back end's "Restore" module.
    """
    return run_delete(backend, "contao:event:delete", event_id)


# --- the calendar: the container an event lives in ------------------------


def calendar_read(backend: ContaoBackend, calendar_id: int) -> dict:
    """Read all fields of a tl_calendar record."""
    return run_json_or_raw(backend, f"contao:calendar:read {int(calendar_id)}")


def calendar_create(backend: ContaoBackend, title: str,
                    fields: dict | None = None) -> dict:
    """Create a calendar.

    Same shape as a news archive: `jumpTo` is mandatory in the palette (the
    page rendering a single event), `groups` only once `protected=1` opens its
    subpalette.
    """
    cmd = f"contao:calendar:create --title={shlex.quote(title)} --no-interaction"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def calendar_update(backend: ContaoBackend, calendar_id: int, fields: dict) -> dict:
    """Update a calendar."""
    return run_update(backend, "contao:calendar:update", calendar_id, fields)


def calendar_delete(backend: ContaoBackend, calendar_id: int) -> dict:
    """Delete a calendar with every event in it.

    Chain: tl_calendar_events -> tl_content. One `tl_undo` entry for the set.
    """
    return run_delete(backend, "contao:calendar:delete", calendar_id)
