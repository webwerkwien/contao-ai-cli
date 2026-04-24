"""
news group — Manage Contao news entries (tl_news).
"""
import click

from cli_anything.contao.core import session as session_mod, news as news_mod
from .helpers import _get_backend, _output, _require_bridge


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
    _require_bridge(ctx, "news read")
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
    """Create a news entry via contao-cli-bridge."""
    _require_bridge(ctx, "news create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_create(b, headline, pid, date, parsed),
            as_json or ctx.obj.get("as_json"))
