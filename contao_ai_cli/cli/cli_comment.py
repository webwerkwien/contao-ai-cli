"""
comment group — Manage Contao comments (tl_comments).
"""
import click

from contao_ai_cli.core import session as session_mod, comment as comment_mod
from .helpers import _get_backend, _output, _require_core_bundle, confirm_delete


@click.group()
def comment():
    """Manage Contao comments (tl_comments)."""
    pass


@comment.command("list")
@click.option("--source", default=None,
              help="Filter by source table (e.g. tl_news, tl_page)")
@click.option("--parent", "parent_id", type=int, default=None,
              help="Filter by parent record ID")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def comment_list_cmd(ctx, source, parent_id, limit, offset):
    """List comments, optionally filtered by source and/or parent ID."""
    _require_core_bundle(ctx, "comment list")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(comment_mod.comment_list(b, source, parent_id, limit, offset), ctx.obj.get("as_json"))


@comment.command("delete")
@click.argument("comment_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def comment_delete_cmd(ctx, comment_id, yes, as_json):
    """Delete a comment."""
    _require_core_bundle(ctx, "comment delete")
    if not confirm_delete(f"comment {comment_id}", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(comment_mod.comment_delete(b, comment_id), as_json or ctx.obj.get("as_json"))


@comment.command("publish")
@click.argument("comment_id", type=int)
@click.option("--unpublish", is_flag=True, help="Unpublish instead of publish")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def comment_publish_cmd(ctx, comment_id, unpublish, as_json):
    """Publish or unpublish a comment — the moderation path for visitor text."""
    _require_core_bundle(ctx, "comment publish")
    b = _get_backend(ctx.obj.get("session"))
    _output(comment_mod.comment_publish(b, comment_id, not unpublish),
            as_json or ctx.obj.get("as_json"))
