"""
comment group — Manage Contao comments (tl_comments).
"""
import click

from cli_anything.contao.core import session as session_mod, comment as comment_mod
from .helpers import _get_backend, _output


@click.group()
def comment():
    """Manage Contao comments (tl_comments)."""
    pass


@comment.command("list")
@click.option("--source", default=None,
              help="Filter by source table (e.g. tl_news, tl_page)")
@click.option("--parent", "parent_id", type=int, default=None,
              help="Filter by parent record ID")
@click.pass_context
def comment_list_cmd(ctx, source, parent_id):
    """List comments, optionally filtered by source and/or parent ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(comment_mod.comment_list(b, source, parent_id), ctx.obj.get("as_json"))
