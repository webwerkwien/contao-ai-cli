"""
event group — Manage Contao calendar events (tl_calendar_events).
"""
import click

from contao_ai_cli.core import session as session_mod, event as event_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


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
    _require_core_bundle(ctx, "event read")
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
    _require_core_bundle(ctx, "event create")
    parsed = parse_set_fields(fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.event_create(b, title, pid, start_date, end_date, parsed),
            as_json or ctx.obj.get("as_json"))


@event.command("update")
@click.argument("event_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_update_cmd(ctx, event_id, ids, ids_from_file, fields, as_json):
    """Update fields of an event, or of many at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.
    """
    _require_core_bundle(ctx, "event update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:event:update", event_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@event.command("delete")
@click.argument("event_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_delete_cmd(ctx, event_id, yes, as_json):
    """Delete an event and its content elements."""
    _require_core_bundle(ctx, "event delete")
    if not confirm_delete(f"event {event_id} and its content elements", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.event_delete(b, event_id), as_json or ctx.obj.get("as_json"))


# --- the parent record ----------------------------------------------------


@event.command("calendar-read")
@click.argument("calendar_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def calendar_read_cmd(ctx, calendar_id, as_json):
    """Read all fields of a calendar."""
    _require_core_bundle(ctx, "event calendar-read")
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.calendar_read(b, calendar_id), as_json or ctx.obj.get("as_json"))


@event.command("calendar-create")
@click.option("--title", required=True, help="calendar title")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def calendar_create_cmd(ctx, title, fields, as_json):
    """Create a calendar.

    Only --title is an option here; what else is required comes from the DCA,
    so the command reports it rather than this help text going stale.
    (jumpTo is the page that renders a single event; groups only for a protected calendar.)
    """
    _require_core_bundle(ctx, "event calendar-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.calendar_create(b, title, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@event.command("calendar-update")
@click.argument("calendar_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def calendar_update_cmd(ctx, calendar_id, ids, ids_from_file, fields, as_json):
    """Update a calendar, or many at once."""
    _require_core_bundle(ctx, "event calendar-update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:calendar:update", calendar_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@event.command("calendar-delete")
@click.argument("calendar_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def calendar_delete_cmd(ctx, calendar_id, yes, as_json):
    """Delete a calendar with everything in it.

    Restorable as one entry with `undo restore`, but the cascade is named in
    the prompt because it is not visible from the command name.
    """
    _require_core_bundle(ctx, "event calendar-delete")
    if not confirm_delete(
        f"calendar {calendar_id} AND every event in it and their content elements",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.calendar_delete(b, calendar_id), as_json or ctx.obj.get("as_json"))
