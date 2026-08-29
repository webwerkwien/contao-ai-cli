"""
page group — Manage Contao pages (tl_page).
"""
import click

from contao_ai_cli.core import session as session_mod, page as page_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def page():
    """Manage Contao pages (tl_page)."""
    pass


@page.command("list")
@click.option("--pid", type=int, default=None, help="Filter by parent page ID")
@click.pass_context
def page_list_cmd(ctx, pid):
    """List pages, optionally filtered by parent ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(page_mod.page_list(b, pid), ctx.obj.get("as_json"))


@page.command("tree")
@click.pass_context
def page_tree_cmd(ctx):
    """Show page tree (nested structure)."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(page_mod.page_tree(b), ctx.obj.get("as_json"))


@page.command("read")
@click.argument("page_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_read_cmd(ctx, page_id, as_json):
    """Read all fields of a page record (incl. effective layout)."""
    _require_core_bundle(ctx, "page read")
    b = _get_backend(ctx.obj.get("session"))
    _output(page_mod.page_read(b, page_id), as_json or ctx.obj.get("as_json"))


@page.command("create")
@click.option("--title", required=True, help="Page title")
@click.option("--pid", type=int, default=0, show_default=True, help="Parent page ID")
@click.option("--type", "page_type", default="regular", show_default=True, help="Page type (regular, root, …)")
@click.option("--alias", default="", help="Page alias (auto-generated if omitted)")
@click.option("--language", default="de", show_default=True, help="Page language")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE", help="Extra fields, e.g. --set robots=noindex")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_create_cmd(ctx, title, pid, page_type, alias, language, fields, as_json):
    """Create a page via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "page create")
    parsed = parse_set_fields(fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(page_mod.page_create(b, title, pid, page_type, alias, language, parsed),
            as_json or ctx.obj.get("as_json"))


@page.command("update")
@click.argument("page_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_update_cmd(ctx, page_id, ids, ids_from_file, fields, as_json):
    """Update fields of a page, or of many pages at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.
    """
    _require_core_bundle(ctx, "page update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:page:update", page_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@page.command("delete")
@click.argument("page_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_delete_cmd(ctx, page_id, yes, as_json):
    """Delete a page and its subpages, articles and content elements."""
    _require_core_bundle(ctx, "page delete")
    if not confirm_delete(f"page {page_id} and its subpages, articles and content elements", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(page_mod.page_delete(b, page_id), as_json or ctx.obj.get("as_json"))


@page.command("publish")
@click.argument("page_id", type=int)
@click.option("--unpublish", is_flag=True, help="Unpublish instead of publish")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_publish_cmd(ctx, page_id, unpublish, as_json):
    """Publish or unpublish a page."""
    _require_core_bundle(ctx, "page publish")
    b = _get_backend(ctx.obj.get("session"))
    _output(page_mod.page_publish(b, page_id, not unpublish),
            as_json or ctx.obj.get("as_json"))
