"""
article group — Manage Contao articles (tl_article).
"""
import click

from cli_anything.contao.core import session as session_mod, article as article_mod
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def article():
    """Manage Contao articles (tl_article)."""
    pass


@article.command("list")
@click.option("--page", "page_id", type=int, default=None,
              help="Filter by page ID (pid)")
@click.pass_context
def article_list_cmd(ctx, page_id):
    """List articles, optionally filtered by page ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(article_mod.article_list(b, page_id), ctx.obj.get("as_json"))


@article.command("read")
@click.argument("article_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def article_read_cmd(ctx, article_id, as_json):
    """Read all fields of an article record."""
    _require_bridge(ctx, "article read")
    b = _get_backend(ctx.obj.get("session"))
    _output(article_mod.article_read(b, article_id), as_json or ctx.obj.get("as_json"))


@article.command("create")
@click.option("--title", required=True, help="Article title")
@click.option("--pid", type=int, required=True, help="Parent page ID")
@click.option("--column", "in_column", default="main", show_default=True, help="Layout column")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def article_create_cmd(ctx, title, pid, in_column, fields, as_json):
    """Create an article via contao-cli-bridge."""
    _require_bridge(ctx, "article create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(article_mod.article_create(b, title, pid, in_column, parsed),
            as_json or ctx.obj.get("as_json"))
