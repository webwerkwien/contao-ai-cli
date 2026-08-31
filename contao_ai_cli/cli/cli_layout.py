"""
layout group — Manage Contao layouts (tl_layout).
"""
import click

from contao_ai_cli.core import layout as layout_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def layout():
    """Manage Contao layouts (tl_layout)."""
    pass


@layout.command("list")
@click.option("--theme", "theme_id", type=int, default=None, help="Only layouts of this theme ID")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def layout_list_cmd(ctx, theme_id, as_json):
    """List layouts with the fields that identify them."""
    _require_core_bundle(ctx, "layout list")
    b = _get_backend(ctx.obj.get("session"))
    _output(layout_mod.layout_list(b, theme_id), as_json or ctx.obj.get("as_json"))


@layout.command("read")
@click.argument("layout_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def layout_read_cmd(ctx, layout_id, as_json):
    """Read all fields of a layout record."""
    _require_core_bundle(ctx, "layout read")
    b = _get_backend(ctx.obj.get("session"))
    _output(layout_mod.layout_read(b, layout_id), as_json or ctx.obj.get("as_json"))


@layout.command("create")
@click.option("--theme", "theme_id", type=int, required=True, help="Theme ID (tl_theme) the layout belongs to")
@click.option("--name", required=True, help="Layout name")
@click.option("--template", required=True,
              help='Layout template. "fe_page" is the classic legacy value; a modern '
                   'layout takes a page/layout Twig template.')
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Any other column, e.g. --set width=1200")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def layout_create_cmd(ctx, theme_id, name, template, fields, as_json):
    """Create a page layout under a theme.

    \b
    The layout arrives without sections and without modules — both are wizard
    columns holding serialized structures, and a layout with no modules renders
    nothing. Fill them in afterwards, in the back end or via --set.
    """
    _require_core_bundle(ctx, "layout create")
    b = _get_backend(ctx.obj.get("session"))
    _output(layout_mod.layout_create(b, theme_id, name, template, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@layout.command("update")
@click.argument("layout_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def layout_update_cmd(ctx, layout_id, ids, ids_from_file, fields, as_json):
    """Update fields of a layout, or of many at once.

    \b
    `width`, `headerHeight`, `footerHeight`, `widthLeft` and `widthRight` are
    unit fields: pass a plain number and the record keeps its existing unit
    (px if it had none). Add --set width_unit=rem to change the unit itself.
    """
    _require_core_bundle(ctx, "layout update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:layout:update", layout_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@layout.command("delete")
@click.argument("layout_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def layout_delete_cmd(ctx, layout_id, yes, as_json):
    """Delete a page layout.

    Pages using it are not touched — they fall back to their parent's layout,
    which is Contao's own behaviour for a missing one.
    """
    _require_core_bundle(ctx, "layout delete")
    if not confirm_delete(f"layout {layout_id}", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(layout_mod.layout_delete(b, layout_id), as_json or ctx.obj.get("as_json"))
