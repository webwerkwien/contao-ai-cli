"""
newsletter group — Manage Contao newsletters (tl_newsletter).
"""
import click

from cli_anything.contao.core import session as session_mod, newsletter as newsletter_mod
from .helpers import _get_backend, _output


@click.group()
def newsletter():
    """Manage Contao newsletters (tl_newsletter)."""
    pass


@newsletter.command("channels")
@click.pass_context
def newsletter_channels(ctx):
    """List all newsletter channels."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.channel_list(b), ctx.obj.get("as_json"))


@newsletter.command("list")
@click.option("--channel", "channel_id", type=int, default=None,
              help="Filter by channel ID")
@click.pass_context
def newsletter_list_cmd(ctx, channel_id):
    """List newsletters, optionally filtered by channel ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.newsletter_list(b, channel_id), ctx.obj.get("as_json"))


@newsletter.command("subscribers")
@click.option("--channel", "channel_id", type=int, default=None,
              help="Filter by channel ID")
@click.pass_context
def newsletter_subscribers(ctx, channel_id):
    """List newsletter subscribers."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.subscriber_list(b, channel_id), ctx.obj.get("as_json"))
