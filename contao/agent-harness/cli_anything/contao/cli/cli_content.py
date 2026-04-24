"""
content group — Manage Contao content elements (tl_content).
"""
import click

from cli_anything.contao.core import session as session_mod, content as content_mod
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def content():
    """Manage Contao content elements (tl_content)."""
    pass


@content.command("list")
@click.option("--article", "article_id", type=int, default=None,
              help="Filter by article ID (pid)")
@click.pass_context
def content_list_cmd(ctx, article_id):
    """List content elements, optionally filtered by article ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(content_mod.content_list(b, article_id), ctx.obj.get("as_json"))


@content.command("read")
@click.argument("content_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_read_cmd(ctx, content_id, as_json):
    """Read all fields of a content element record (headline deserialized)."""
    _require_bridge(ctx, "content read")
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
    """Create a content element via contao-cli-bridge."""
    _require_bridge(ctx, "content create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    if text is not None:
        parsed.setdefault("text", text)
    b = _get_backend(ctx.obj.get("session"))
    _output(content_mod.content_create(b, el_type, pid, ptable, parsed),
            as_json or ctx.obj.get("as_json"))
