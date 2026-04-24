"""
event group — Manage Contao calendar events (tl_calendar_events).
"""
import click

from cli_anything.contao.core import session as session_mod, event as event_mod
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def event():
    """Manage Contao calendar events (tl_calendar_events)."""
    pass


@event.command("calendars")
@click.pass_context
def event_calendars(ctx):
    """List all calendars."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(event_mod.calendar_list(b), ctx.obj.get("as_json"))


@event.command("list")
@click.option("--calendar", "calendar_id", type=int, default=None,
              help="Filter by calendar ID")
@click.pass_context
def event_list_cmd(ctx, calendar_id):
    """List calendar events, optionally filtered by calendar ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(event_mod.event_list(b, calendar_id), ctx.obj.get("as_json"))


@event.command("read")
@click.argument("event_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_read_cmd(ctx, event_id, as_json):
    """Read all fields of a calendar event record."""
    _require_bridge(ctx, "event read")
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.event_read(b, event_id), as_json or ctx.obj.get("as_json"))


@event.command("create")
@click.option("--title", required=True, help="Event title")
@click.option("--pid", type=int, required=True, help="Calendar ID")
@click.option("--start-date", "start_date", default=None, help="Start date (YYYY-MM-DD, default: today)")
@click.option("--end-date", "end_date", default=None, help="End date (YYYY-MM-DD, default: start date)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_create_cmd(ctx, title, pid, start_date, end_date, fields, as_json):
    """Create a calendar event via contao-ai-core-bundle."""
    _require_bridge(ctx, "event create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.event_create(b, title, pid, start_date, end_date, parsed),
            as_json or ctx.obj.get("as_json"))
