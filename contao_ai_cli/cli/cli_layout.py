"""
layout group — Manage Contao layouts (tl_layout).
"""
import click

from contao_ai_cli.core import layout as layout_mod
from .helpers import _get_backend, _output, _require_core_bundle


@click.group()
def layout():
    """Manage Contao layouts (tl_layout)."""
    pass


@layout.command("read")
@click.argument("layout_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def layout_read_cmd(ctx, layout_id, as_json):
    """Read all fields of a layout record."""
    _require_core_bundle(ctx, "layout read")
    b = _get_backend(ctx.obj.get("session"))
    _output(layout_mod.layout_read(b, layout_id), as_json or ctx.obj.get("as_json"))
