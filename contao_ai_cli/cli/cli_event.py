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
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def event_calendars(ctx, limit, offset):
    """List all calendars."""
    _require_core_bundle(ctx, "event calendars")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(event_mod.calendar_list(b, limit, offset), ctx.obj.get("as_json"))


@event.command("list")
@click.option("--calendar", "--pid", "calendar_id", type=int, default=None,
              help="Filter by calendar ID (or --pid, the name create uses)")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def event_list_cmd(ctx, calendar_id, limit, offset):
    """List calendar events, optionally filtered by calendar ID."""
    _require_core_bundle(ctx, "event list")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(event_mod.event_list(b, calendar_id, limit, offset), ctx.obj.get("as_json"))


@event.command("read")
@click.argument("event_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_read_cmd(ctx, event_id, as_json):
    """Read all fields of a calendar event record."""
    _require_core_bundle(ctx, "event read")
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.event_read(b, event_id), as_json or ctx.obj.get("as_json"))


def _refuse_empty_date_options(**values):
    """An empty date or time option would be dropped and answer as if not given."""
    for name, value in values.items():
        if value is not None and not value.strip():
            hint = " To make it a one-day event, use --set endDate=" if name == "end_date" else ""
            raise click.UsageError(f"--{name.replace('_', '-')} is empty.{hint}")


@event.command("create")
@click.option("--title", required=True, help="Event title")
@click.option("--pid", type=int, required=True, help="Calendar ID")
@click.option("--start-date", "start_date", default=None, help="Start date (YYYY-MM-DD, default: today)")
@click.option("--end-date", "end_date", default=None,
              help="Last day of an event over several days (YYYY-MM-DD); leave out for one day")
@click.option("--start-time", "start_time", default=None,
              help="Start time (HH:MM); without it the event lasts all day")
@click.option("--end-time", "end_time", default=None, help="End time (HH:MM), needs --start-time")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_create_cmd(ctx, title, pid, start_date, end_date, start_time, end_time, fields, as_json):
    """Create a calendar event via contao-ai-core-bundle.

    The stored start and end are derived from the dates and times as in the back
    end (core-bundle v0.28.0): an all-day event ends at 23:59:59 of its last day.
    """
    _require_core_bundle(ctx, "event create")
    _refuse_empty_date_options(start_date=start_date, end_date=end_date,
                               start_time=start_time, end_time=end_time)
    parsed = parse_set_fields(fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.event_create(b, title, pid, start_date, end_date, parsed,
                                   start_time=start_time, end_time=end_time),
            as_json or ctx.obj.get("as_json"))


@event.command("update")
@click.argument("event_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--start-date", "start_date", default=None, help="New start date (YYYY-MM-DD)")
@click.option("--end-date", "end_date", default=None,
              help="New last day (YYYY-MM-DD); --set endDate= makes it a one-day event")
@click.option("--start-time", "start_time", default=None, help="New start time (HH:MM)")
@click.option("--end-time", "end_time", default=None, help="New end time (HH:MM)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_update_cmd(ctx, event_id, ids, ids_from_file, fields, start_date, end_date,
                     start_time, end_time, as_json):
    """Update fields of an event, or of many at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.

    Dates and times go through --start-date/--end-date/--start-time/--end-time;
    the stored start and end follow from them as in the back end. --set
    addTime=0 turns an event with a time back into an all-day one.
    """
    _require_core_bundle(ctx, "event update")
    _refuse_empty_date_options(start_date=start_date, end_date=end_date,
                               start_time=start_time, end_time=end_time)
    options = event_mod.date_options(start_date, end_date, start_time, end_time)
    parsed = parse_set_fields(fields)
    if not parsed and not options:
        raise click.UsageError("Nothing to change: give --set FIELD=VALUE or a date/time option.")
    b = _get_backend(ctx.obj.get("session"))
    command = "contao:event:update" + (" " + options if options else "")
    _output(dispatch_update(b, command, event_id, ids, ids_from_file, parsed),
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
