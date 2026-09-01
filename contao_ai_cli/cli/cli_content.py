"""
content group — Manage Contao content elements (tl_content).
"""
import click

from contao_ai_cli.core import session as session_mod, content as content_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def content():
    """Manage Contao content elements (tl_content)."""
    pass


@content.command("list")
@click.option("--article", "article_id", type=int, default=None,
              help="Filter by article ID (pid)")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def content_list_cmd(ctx, article_id, limit, offset):
    """List content elements, optionally filtered by article ID."""
    _require_core_bundle(ctx, "content list")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(content_mod.content_list(b, article_id, limit, offset), ctx.obj.get("as_json"))


@content.command("read")
@click.argument("content_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_read_cmd(ctx, content_id, as_json):
    """Read all fields of a content element record (headline deserialized)."""
    _require_core_bundle(ctx, "content read")
    b = _get_backend(ctx.obj.get("session"))
    _output(content_mod.content_read(b, content_id), as_json or ctx.obj.get("as_json"))


@content.command("create")
@click.option("--type", "el_type", required=True, help="Element type (text, headline, image, …)")
@click.option("--pid", type=int, required=True, help="Parent ID (article ID)")
@click.option("--ptable", default="tl_article", show_default=True, help="Parent table")
@click.option("--text", default=None, help="Shortcut for --set text=VALUE")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_create_cmd(ctx, el_type, pid, ptable, text, fields, as_json):
    """Create a content element via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "content create")
    parsed = parse_set_fields(fields)
    if text is not None:
        parsed.setdefault("text", text)
    b = _get_backend(ctx.obj.get("session"))
    _output(content_mod.content_create(b, el_type, pid, ptable, parsed),
            as_json or ctx.obj.get("as_json"))


@content.command("update")
@click.argument("content_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_update_cmd(ctx, content_id, ids, ids_from_file, fields, as_json):
    """Update fields of a content element, or of many at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.
    """
    _require_core_bundle(ctx, "content update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:content:update", content_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@content.command("delete")
@click.argument("content_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_delete_cmd(ctx, content_id, yes, as_json):
    """Delete a content element and nested content elements."""
    _require_core_bundle(ctx, "content delete")
    if not confirm_delete(f"content element {content_id} and nested content elements", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(content_mod.content_delete(b, content_id), as_json or ctx.obj.get("as_json"))
