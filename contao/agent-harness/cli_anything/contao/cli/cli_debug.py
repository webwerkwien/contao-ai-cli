"""
debug group — Debug and inspection tools.
"""
import shlex
import click

from cli_anything.contao.core import debug_ops
from .helpers import _get_backend, _output


@click.group()
def debug():
    """Debug and inspection tools."""


@debug.command("twig")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_twig(ctx, as_json):
    """Display Contao template hierarchy."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_contao_twig(b), as_json or ctx.obj.get("as_json"))


@debug.command("dca")
@click.argument("table")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_dca(ctx, table, as_json):
    """Dump DCA configuration for a table."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_dca(b, table), as_json or ctx.obj.get("as_json"))


@debug.command("pages")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_pages(ctx, as_json):
    """Display page controller configuration."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_pages(b), as_json or ctx.obj.get("as_json"))


@debug.command("plugins")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_plugins(ctx, as_json):
    """Display Contao Manager plugin configurations."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_plugins(b), as_json or ctx.obj.get("as_json"))


@debug.command("router")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_router(ctx, as_json):
    """Display current routes."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_router(b), as_json or ctx.obj.get("as_json"))


@debug.command("match")
@click.argument("path_info")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_match(ctx, path_info, as_json):
    """Match a URL path to its Symfony route."""
    b = _get_backend(ctx.obj.get("session"))
    result = b.run(f"router:match {shlex.quote(path_info)}")
    _output({"output": result["stdout"]}, as_json or ctx.obj.get("as_json"))
