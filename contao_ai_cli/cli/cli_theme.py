"""
theme group — Manage Contao themes (tl_theme).
"""
import click

from contao_ai_cli.core import theme as theme_mod
from contao_ai_cli.core import theme_archive as archive_mod
from contao_ai_cli.core.status import cli_prefix
from .cli_health import _session_name
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    confirm_escalation, dispatch_update, parse_set_fields,
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


@theme.command("export")
@click.argument("theme_id", type=int)
@click.option("--to", "local_path", default=None, help="Local file to write (default: <theme name>.cto here)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def theme_export_cmd(ctx, theme_id, local_path, as_json):
    """Export a theme as Contao's .cto and download it (core-bundle v1.9.0).

    Contao's own export: theme, image sizes, modules, layouts and the theme's files and
    templates. Theme elements are not part of a .cto. The copy on the server is removed.
    """
    _require_core_bundle(ctx, "theme export")
    b = _get_backend(ctx.obj.get("session"))
    try:
        result = archive_mod.theme_export(b, theme_id, local_path)
    except archive_mod.ArchiveError as e:
        raise click.ClickException(str(e))
    _output(result, as_json or ctx.obj.get("as_json"))
    if result.get("status") == "error":
        ctx.exit(1)


@theme.command("import")
@click.argument("local_file", type=click.Path(dir_okay=False))
@click.option("--yes", "-y", "assume_yes", is_flag=True,
              help="Import after the preview without asking; an agent passes it only after asking the operator")
@click.option("--operator", default="", help="Acting user identifier for the audit log")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def theme_import_cmd(ctx, local_file, assume_yes, operator, as_json):
    """Import a theme from Contao's .cto (core-bundle v1.9.0).

    First a preview: the theme, rows per table, the files in files/ and templates/ it
    would OVERWRITE, fields this database lacks, layout slots that will stay empty (a .cto
    holds no theme elements). An import has no undo. At a terminal you are asked; without
    one the preview is the answer, and `--yes` imports. Example websites (.sql) have
    their own command: `example-website import`.
    """
    _require_core_bundle(ctx, "theme import")
    as_json = as_json or ctx.obj.get("as_json")
    b = _get_backend(ctx.obj.get("session"))
    try:
        with archive_mod.Upload(b, local_file, archive_mod.THEME_EXTENSIONS) as remote:
            preview = archive_mod.theme_import(b, remote, confirm=False)
            if preview.get("status") != "preview":
                _output(preview, as_json)
                ctx.exit(1)
            if not assume_yes and not confirm_escalation(
                    f"Import theme {', '.join(preview.get('themes') or [])}? "
                    f"{len(preview.get('overwrites') or [])} existing file(s) would be overwritten."):
                _output({**preview, "imported": False,
                         "next": "Nothing was imported. Show the preview to the operator; with their yes, repeat with --yes."},
                        as_json)
                return
            result = archive_mod.theme_import(b, remote, confirm=True, operator=operator)
    except archive_mod.ArchiveError as e:
        raise click.ClickException(str(e))
    if result.get("status") == "ok":
        # The import writes templates; in production Contao keeps the template hierarchy
        # in a cache pool until it is cleared.
        result["nextSteps"] = [{"command": f"{cli_prefix(_session_name(ctx.obj.get('session')))} cache clear",
                                "optional": False,
                                "reason": "The theme's templates and layouts are new; caches still hold the old state."}]
    _output(result, as_json)
    if result.get("status") != "ok":
        ctx.exit(1)
