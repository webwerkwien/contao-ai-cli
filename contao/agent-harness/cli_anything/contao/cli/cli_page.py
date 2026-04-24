"""
page group — Manage Contao pages (tl_page).
"""
import click

from cli_anything.contao.core import session as session_mod, page as page_mod
from .helpers import _get_backend, _output, _require_bridge


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
    _require_bridge(ctx, "page read")
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
    _require_bridge(ctx, "page create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(page_mod.page_create(b, title, pid, page_type, alias, language, parsed),
            as_json or ctx.obj.get("as_json"))
