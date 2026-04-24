"""
search group — Search index management (cmsig/seal).
"""
import click

from cli_anything.contao.core import search as search_mod
from .helpers import _get_backend, _output


@click.group()
def search():
    """Search index management (cmsig/seal)."""


@search.command("reindex")
@click.option("--index", default="", help="Specific index name (all if omitted)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_reindex(ctx, index, as_json):
    """Rebuild the search index."""
    b = _get_backend(ctx.obj.get("session"))
    _output(search_mod.search_reindex(b, index), as_json or ctx.obj.get("as_json"))


@search.command("index-create")
@click.option("--index", default="", help="Specific index name (all if omitted)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_index_create(ctx, index, as_json):
    """Create search index."""
    b = _get_backend(ctx.obj.get("session"))
    _output(search_mod.search_index_create(b, index), as_json or ctx.obj.get("as_json"))


@search.command("index-drop")
@click.option("--index", default="", help="Specific index name (all if omitted)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_index_drop(ctx, index, as_json):
    """Drop search index."""
    b = _get_backend(ctx.obj.get("session"))
    _output(search_mod.search_index_drop(b, index), as_json or ctx.obj.get("as_json"))
