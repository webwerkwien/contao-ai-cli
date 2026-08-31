"""
theme group — Manage Contao themes (tl_theme).
"""
import click

from contao_ai_cli.core import theme as theme_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def theme():
    """Manage Contao themes (tl_theme) — the root of the theme layer."""
    pass


@theme.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def theme_list_cmd(ctx, as_json):
    """List all themes."""
    _require_core_bundle(ctx, "theme list")
    b = _get_backend(ctx.obj.get("session"))
    _output(theme_mod.theme_list(b), as_json or ctx.obj.get("as_json"))


@theme.command("read")
@click.argument("theme_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def theme_read_cmd(ctx, theme_id, as_json):
    """Read all fields of a theme record."""
    _require_core_bundle(ctx, "theme read")
    b = _get_backend(ctx.obj.get("session"))
    _output(theme_mod.theme_read(b, theme_id), as_json or ctx.obj.get("as_json"))


@theme.command("create")
@click.option("--name", required=True, help="Theme name")
@click.option("--author", required=True,
              help="Author credit line — free text, not a user ID")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def theme_create_cmd(ctx, name, author, fields, as_json):
    """Create a theme."""
    _require_core_bundle(ctx, "theme create")
    b = _get_backend(ctx.obj.get("session"))
    _output(theme_mod.theme_create(b, name, author, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@theme.command("update")
@click.argument("theme_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def theme_update_cmd(ctx, theme_id, ids, ids_from_file, fields, as_json):
    """Update fields of a theme, or of many at once."""
    _require_core_bundle(ctx, "theme update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:theme:update", theme_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@theme.command("delete")
@click.argument("theme_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def theme_delete_cmd(ctx, theme_id, yes, as_json):
    """Delete a theme with its modules, layouts and image sizes.

    This is the widest cascade the CLI can trigger. Everything is restorable
    from the back end as one entry, but on a real site it is a lot of rows.
    """
    _require_core_bundle(ctx, "theme delete")
    if not confirm_delete(
        f"theme {theme_id} AND all its modules, layouts, image sizes "
        f"(with their media-query variants) and theme content elements",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(theme_mod.theme_delete(b, theme_id), as_json or ctx.obj.get("as_json"))
