"""
image-size group — Manage Contao image sizes (tl_image_size).
"""
import click

from contao_ai_cli.core import image_size as size_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group("image-size")
def image_size():
    """Manage Contao image sizes (tl_image_size)."""
    pass


@image_size.command("list")
@click.option("--theme", "theme_id", type=int, default=None, help="Only sizes of this theme ID")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_list_cmd(ctx, theme_id, as_json):
    """List image sizes with the fields that identify them.

    Shows `sizes` and `densities` alongside `width`, because those are what
    decide which variant a browser actually loads.
    """
    _require_core_bundle(ctx, "image-size list")
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_list(b, theme_id), as_json or ctx.obj.get("as_json"))


@image_size.command("read")
@click.argument("size_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_read_cmd(ctx, size_id, as_json):
    """Read all fields of an image size record."""
    _require_core_bundle(ctx, "image-size read")
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_read(b, size_id), as_json or ctx.obj.get("as_json"))


@image_size.command("create")
@click.option("--name", required=True, help='Name shown in the back end, e.g. "Tourenbild"')
@click.option("--theme", "pid", type=int, required=True, help="Theme ID (tl_theme) the size belongs to")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Any other column, e.g. --set width=1600")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_create_cmd(ctx, name, pid, fields, as_json):
    """Create an image size under a theme.

    \b
    Set `sizes` and `densities`, not just a width — they are what the browser
    evaluates to pick a variant:
      contao-ai-cli image-size create --theme 1 --name "Tourenbild" \\
          --set width=1600 \\
          --set sizes="(max-width: 1100px) 100vw, 1000px" \\
          --set densities="600w, 1000w, 1300w, 1600w"
    """
    _require_core_bundle(ctx, "image-size create")
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_create(b, name, pid, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@image_size.command("update")
@click.argument("size_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_update_cmd(ctx, size_id, ids, ids_from_file, fields, as_json):
    """Update fields of an image size, or of many at once.

    Give one ID, or --ids=3,5 / --ids-from-file ids.txt to change several in a
    single connection. Every record is versioned individually either way.
    """
    _require_core_bundle(ctx, "image-size update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:image-size:update", size_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@image_size.command("delete")
@click.argument("size_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_delete_cmd(ctx, size_id, yes, as_json):
    """Delete an image size and its media-query variants."""
    _require_core_bundle(ctx, "image-size delete")
    if not confirm_delete(f"image size {size_id} and its media-query variants", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_delete(b, size_id), as_json or ctx.obj.get("as_json"))


# ── media-query variants ─────────────────────────────────────────────────────


@image_size.command("items")
@click.argument("size_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_items_cmd(ctx, size_id, as_json):
    """List the media-query variants of an image size, in sort order."""
    _require_core_bundle(ctx, "image-size items")
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_items(b, size_id), as_json or ctx.obj.get("as_json"))


@image_size.command("item-read")
@click.argument("item_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_item_read_cmd(ctx, item_id, as_json):
    """Read all fields of one media-query variant."""
    _require_core_bundle(ctx, "image-size item-read")
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_item_read(b, item_id), as_json or ctx.obj.get("as_json"))


@image_size.command("item-create")
@click.option("--size", "size_id", type=int, required=True, help="Image size ID the variant belongs to")
@click.option("--media", required=True, help='CSS media condition, e.g. "(max-width: 767px)"')
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Any other column, e.g. --set width=400")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_item_create_cmd(ctx, size_id, media, fields, as_json):
    """Create a media-query variant under an image size.

    \b
      contao-ai-cli image-size item-create --size 6 \\
          --media "(max-width: 767px)" \\
          --set width=400 --set densities="400w, 800w"

    Variants are appended; the server assigns the next sort position.
    """
    _require_core_bundle(ctx, "image-size item-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_item_create(b, size_id, media, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@image_size.command("item-update")
@click.argument("item_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_item_update_cmd(ctx, item_id, ids, ids_from_file, fields, as_json):
    """Update fields of a media-query variant, or of many at once."""
    _require_core_bundle(ctx, "image-size item-update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:image-size-item:update", item_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@image_size.command("item-delete")
@click.argument("item_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def image_size_item_delete_cmd(ctx, item_id, yes, as_json):
    """Delete a single media-query variant, leaving its image size in place."""
    _require_core_bundle(ctx, "image-size item-delete")
    if not confirm_delete(f"media-query variant {item_id}", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(size_mod.image_size_item_delete(b, item_id), as_json or ctx.obj.get("as_json"))
