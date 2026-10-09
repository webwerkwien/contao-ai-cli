"""
content group — Manage Contao content elements (tl_content).
"""
import click

from contao_ai_cli.core import session as session_mod, content as content_mod
from contao_ai_cli.core.contao_ops import run_move
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, check_move_target,
    confirm_delete, dispatch_update, output_move, parse_set_fields,
)


@click.group()
def content():
    """Manage Contao content elements (tl_content)."""
    pass


@content.command("list")
@click.option("--article", "article_id", type=int, default=None,
              help="Only the direct elements of this article (pid + ptable=tl_article)")
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
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--text", default=None, help="Shortcut for --set text=VALUE, as on create")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_update_cmd(ctx, content_id, ids, ids_from_file, fields, text, as_json):
    """Update fields of a content element, or of many at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.
    """
    parsed = parse_set_fields(fields)
    if text is not None:
        parsed.setdefault("text", text)
    if not parsed:
        raise click.UsageError("Nothing to change: give --set FIELD=VALUE or --text.")
    _require_core_bundle(ctx, "content update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:content:update", content_id, ids, ids_from_file, parsed),
            as_json or ctx.obj.get("as_json"))


@content.command("move")
@click.argument("content_id", type=int)
@click.option("--to", "to", type=int, default=None, help="Parent ID (an article by default) — the element goes behind its last element")
@click.option("--after", type=int, default=None, help="Element ID — the element goes directly behind it, in the same parent")
@click.option("--ptable", default=None, help="Parent table for --to (tl_article, tl_news, tl_content, …); default: the element's current one")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_move_cmd(ctx, content_id, to, after, ptable, as_json):
    """Move a content element, as cut and paste in the back end.

    --to 12 puts it into article 12, behind the last element; --after 40 puts it
    directly behind element 40, in that element's article (or news entry, or
    element group). Needs core-bundle v1.2.0.
    """
    check_move_target(to, after, ptable)
    _require_core_bundle(ctx, "content move")
    b = _get_backend(ctx.obj.get("session"))
    output_move(ctx, run_move(b, "contao:content:move", content_id, to=to, after=after, ptable=ptable), as_json)


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
