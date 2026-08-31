"""
news group — Manage Contao news entries (tl_news).
"""
import click

from contao_ai_cli.core import session as session_mod, news as news_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def news():
    """Manage Contao news entries (tl_news)."""
    pass


@news.command("archives")
@click.pass_context
def news_archives(ctx):
    """List all news archives."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(news_mod.news_archive_list(b), ctx.obj.get("as_json"))


@news.command("list")
@click.option("--archive", "archive_id", type=int, default=None,
              help="Filter by archive ID")
@click.pass_context
def news_list_cmd(ctx, archive_id):
    """List news entries, optionally filtered by archive ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(news_mod.news_list(b, archive_id), ctx.obj.get("as_json"))


@news.command("read")
@click.argument("news_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_read_cmd(ctx, news_id, as_json):
    """Read all fields of a news entry (headline deserialized)."""
    _require_core_bundle(ctx, "news read")
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_read(b, news_id), as_json or ctx.obj.get("as_json"))


@news.command("create")
@click.option("--headline", required=True, help="News headline")
@click.option("--pid", type=int, required=True, help="News archive ID")
@click.option("--date", default=None, help="Publication date (YYYY-MM-DD, default: today)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_create_cmd(ctx, headline, pid, date, fields, as_json):
    """Create a news entry via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "news create")
    parsed = parse_set_fields(fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_create(b, headline, pid, date, parsed),
            as_json or ctx.obj.get("as_json"))


@news.command("update")
@click.argument("news_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_update_cmd(ctx, news_id, ids, ids_from_file, fields, as_json):
    """Update fields of a news entry, or of many at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.
    """
    _require_core_bundle(ctx, "news update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:news:update", news_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@news.command("delete")
@click.argument("news_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_delete_cmd(ctx, news_id, yes, as_json):
    """Delete a news entry and its content elements."""
    _require_core_bundle(ctx, "news delete")
    if not confirm_delete(f"news entry {news_id} and its content elements", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_delete(b, news_id), as_json or ctx.obj.get("as_json"))


@news.command("repair-headlines")
@click.option("--dry-run", is_flag=True, help="Report what would change, write nothing")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_repair_headlines_cmd(ctx, dry_run, as_json):
    """Unpack legacy serialized headlines in tl_news (one-off migration)."""
    _require_core_bundle(ctx, "news repair-headlines")
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_repair_headlines(b, dry_run), as_json or ctx.obj.get("as_json"))


# --- the parent record ----------------------------------------------------


@news.command("archive-read")
@click.argument("archive_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_archive_read_cmd(ctx, archive_id, as_json):
    """Read all fields of a news archive."""
    _require_core_bundle(ctx, "news archive-read")
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_archive_read(b, archive_id), as_json or ctx.obj.get("as_json"))


@news.command("archive-create")
@click.option("--title", required=True, help="news archive title")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_archive_create_cmd(ctx, title, fields, as_json):
    """Create a news archive.

    Only --title is an option here; what else is required comes from the DCA,
    so the command reports it rather than this help text going stale.
    (jumpTo is the page that renders a single item; groups only for a protected archive.)
    """
    _require_core_bundle(ctx, "news archive-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_archive_create(b, title, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@news.command("archive-update")
@click.argument("archive_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_archive_update_cmd(ctx, archive_id, ids, ids_from_file, fields, as_json):
    """Update a news archive, or many at once."""
    _require_core_bundle(ctx, "news archive-update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:news-archive:update", archive_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@news.command("archive-delete")
@click.argument("archive_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_archive_delete_cmd(ctx, archive_id, yes, as_json):
    """Delete a news archive with everything in it.

    Restorable as one entry with `undo restore`, but the cascade is named in
    the prompt because it is not visible from the command name.
    """
    _require_core_bundle(ctx, "news archive-delete")
    if not confirm_delete(
        f"news archive {archive_id} AND every news entry in it and their content elements",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_archive_delete(b, archive_id), as_json or ctx.obj.get("as_json"))
