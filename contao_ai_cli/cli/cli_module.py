"""
module group — Manage Contao front end modules (tl_module).
"""
import click

from contao_ai_cli.core import module as module_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def module():
    """Manage Contao front end modules (tl_module)."""
    pass


@module.command("types")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def module_types_cmd(ctx, as_json):
    """List the module types available here, and what each one requires.

    Start here before `create`. A module type's extra requirements come from its
    DCA palette, so this reflects the installation — types added by extensions
    appear too.
    """
    _require_core_bundle(ctx, "module types")
    b = _get_backend(ctx.obj.get("session"))
    _output(module_mod.module_types(b), as_json or ctx.obj.get("as_json"))


@module.command("list")
@click.option("--theme", "theme_id", type=int, default=None, help="Only modules of this theme ID")
@click.option("--type", "module_type", default=None, help="Only modules of this type, e.g. newslist")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def module_list_cmd(ctx, theme_id, module_type, as_json):
    """List modules with the fields that identify them."""
    _require_core_bundle(ctx, "module list")
    b = _get_backend(ctx.obj.get("session"))
    _output(module_mod.module_list(b, theme_id, module_type), as_json or ctx.obj.get("as_json"))


@module.command("read")
@click.argument("module_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def module_read_cmd(ctx, module_id, as_json):
    """Read all fields of a module record."""
    _require_core_bundle(ctx, "module read")
    b = _get_backend(ctx.obj.get("session"))
    _output(module_mod.module_read(b, module_id), as_json or ctx.obj.get("as_json"))


@module.command("create")
@click.option("--theme", "theme_id", type=int, required=True, help="Theme ID (tl_theme) the module belongs to")
@click.option("--name", required=True, help="Module name shown in the back end")
@click.option("--type", "module_type", required=True, help='Module type, e.g. "navigation" — see `module types`')
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Type-specific fields; multi-value ones take a comma list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def module_create_cmd(ctx, theme_id, name, module_type, fields, as_json):
    """Create a front end module under a theme.

    \b
      contao-ai-cli module create --theme 1 --name "News - Latest" --type newslist \\
          --set news_archives=1 --set numberOfItems=5

    What a type requires beyond a name comes from its DCA palette, so the server
    names any missing field rather than guessing. `module types` lists them all.
    """
    _require_core_bundle(ctx, "module create")
    b = _get_backend(ctx.obj.get("session"))
    _output(module_mod.module_create(b, theme_id, name, module_type, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@module.command("update")
@click.argument("module_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def module_update_cmd(ctx, module_id, ids, ids_from_file, fields, as_json):
    """Update fields of a module, or of many at once.

    Multi-value fields take a comma-separated list: --set news_archives=1,3
    """
    _require_core_bundle(ctx, "module update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:module:update", module_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@module.command("delete")
@click.argument("module_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def module_delete_cmd(ctx, module_id, yes, as_json):
    """Delete a front end module.

    Layouts that place it are not touched — Contao skips a module it cannot find.
    """
    _require_core_bundle(ctx, "module delete")
    if not confirm_delete(f"module {module_id}", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(module_mod.module_delete(b, module_id), as_json or ctx.obj.get("as_json"))
