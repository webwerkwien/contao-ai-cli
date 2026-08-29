"""
article group — Manage Contao articles (tl_article).
"""
import click

from contao_ai_cli.core import session as session_mod, article as article_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


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
    _require_core_bundle(ctx, "article read")
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
    """Create an article via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "article create")
    parsed = parse_set_fields(fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(article_mod.article_create(b, title, pid, in_column, parsed),
            as_json or ctx.obj.get("as_json"))


@article.command("update")
@click.argument("article_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def article_update_cmd(ctx, article_id, ids, ids_from_file, fields, as_json):
    """Update fields of an article, or of many at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.
    """
    _require_core_bundle(ctx, "article update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:article:update", article_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@article.command("delete")
@click.argument("article_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def article_delete_cmd(ctx, article_id, yes, as_json):
    """Delete an article and its content elements."""
    _require_core_bundle(ctx, "article delete")
    if not confirm_delete(f"article {article_id} and its content elements", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(article_mod.article_delete(b, article_id), as_json or ctx.obj.get("as_json"))
