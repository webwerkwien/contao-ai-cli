"""Contao calendar event management (tl_calendar_events, tl_calendar)."""
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
