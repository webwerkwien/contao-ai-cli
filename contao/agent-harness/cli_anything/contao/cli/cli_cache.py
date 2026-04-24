"""
cache group — Cache management.
"""
import click

from cli_anything.contao.core import cache as cache_mod
from .helpers import _get_backend, _output


@click.group()
def cache():
    """Cache management."""


@cache.command("clear")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_clear(ctx, as_json):
    """Clear the Contao/Symfony cache."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_clear(b), as_json or ctx.obj.get("as_json"))


@cache.command("warmup")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_warmup(ctx, as_json):
    """Warm up the cache."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_warmup(b), as_json or ctx.obj.get("as_json"))


@cache.command("pool-list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_pool_list(ctx, as_json):
    """List cache pools."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_pool_list(b), as_json or ctx.obj.get("as_json"))


@cache.command("pool-clear")
@click.argument("pool", default="cache.global_clearer")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_pool_clear(ctx, pool, as_json):
    """Clear a specific cache pool."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_pool_clear(b, pool), as_json or ctx.obj.get("as_json"))
