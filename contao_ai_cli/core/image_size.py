"""Contao image sizes (tl_image_size, tl_image_size_item).

The theme layer's first entity in this CLI. Reading arrived on 2026-08-31 with
the generic `record` group; this is the write half.

`image_size_list` is deliberately a preset over `contao:record:list` rather than
a command of its own on the server. The generic command already reads any table
correctly — what it cannot know is which six of the seventeen columns a person
looking at an image size actually wants. That is entity knowledge, and it is
the only thing this function adds.
"""
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    build_set_args, run_delete, run_json_or_raw, run_update,
)

#: What identifies an image size at a glance. `sizes` and `densities` are in
#: here on purpose: they decide which variant a browser loads, and a listing
#: that shows only `width` invites exactly the mistake that made this command
#: necessary — picking a size by its number and getting a different one served.
LIST_FIELDS = "id,pid,name,width,height,sizes,densities"


def image_size_list(backend: ContaoBackend, theme_id: int | None = None) -> dict:
    """List image sizes, optionally only those of one theme."""
    cmd = f"contao:record:list tl_image_size --fields {shlex.quote(LIST_FIELDS)} --order {shlex.quote('name ASC')}"
    if theme_id is not None:
        cmd += f" --filter pid={int(theme_id)}"
    return run_json_or_raw(backend, cmd)


def image_size_read(backend: ContaoBackend, size_id: int) -> dict:
    """Read every field of one tl_image_size record."""
    return run_json_or_raw(backend, f"contao:image-size:read {int(size_id)}")


def image_size_create(backend: ContaoBackend, name: str, pid: int,
                      fields: dict | None = None) -> dict:
    """Create an image size under a theme.

    `pid` is a theme ID and is required — `tl_image_size.ptable` is `tl_theme`,
    so a size belonging to no theme is not something Contao has.
    """
    cmd = (
        f"contao:image-size:create --name={shlex.quote(name)} "
        f"--pid={int(pid)} --no-interaction"
    )
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def image_size_update(backend: ContaoBackend, size_id: int, fields: dict) -> dict:
    """Update image size fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:image-size:update", size_id, fields)


def image_size_delete(backend: ContaoBackend, size_id: int) -> dict:
    """Delete an image size via contao-ai-core-bundle.

    Cascades to its `tl_image_size_item` media-query variants, because Contao's
    own DCA declares them as its child table. Counted live on 2026-08-31: two
    variants, `rowsTotal: 3`, zero orphans left behind, one `tl_undo` row for
    the whole set. Recoverable from the back end's "Restore" module.
    """
    return run_delete(backend, "contao:image-size:delete", size_id)


# ── media-query variants (tl_image_size_item) ────────────────────────────────
#
# This is where an image size stops being a single number: the parent carries
# the fallback, each item says "at this media condition, use these dimensions
# instead". A size with no items serves one variant to every viewport, which is
# valid and usually not what was meant.

#: What identifies a variant. `media` first — it is the condition everything
#: else hangs off.
ITEM_LIST_FIELDS = "id,pid,sorting,media,width,height,sizes,densities,invisible"


def image_size_items(backend: ContaoBackend, size_id: int) -> dict:
    """List the media-query variants of one image size, in their sort order."""
    return run_json_or_raw(
        backend,
        f"contao:record:list tl_image_size_item --filter pid={int(size_id)} "
        f"--fields {shlex.quote(ITEM_LIST_FIELDS)} --order {shlex.quote('sorting ASC')}",
    )


def image_size_item_read(backend: ContaoBackend, item_id: int) -> dict:
    """Read every field of one tl_image_size_item record."""
    return run_json_or_raw(backend, f"contao:image-size-item:read {int(item_id)}")


def image_size_item_create(backend: ContaoBackend, size_id: int, media: str,
                           fields: dict | None = None) -> dict:
    """Create a media-query variant under an image size.

    `media` is the CSS media condition, e.g. `(max-width: 767px)`. It has no
    default: a variant without one competes with the parent for every viewport.
    New variants are appended — the server picks the next `sorting` value.
    """
    cmd = (
        f"contao:image-size-item:create --pid={int(size_id)} "
        f"--media={shlex.quote(media)} --no-interaction"
    )
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def image_size_item_update(backend: ContaoBackend, item_id: int, fields: dict) -> dict:
    """Update fields of a media-query variant."""
    return run_update(backend, "contao:image-size-item:update", item_id, fields)


def image_size_item_delete(backend: ContaoBackend, item_id: int) -> dict:
    """Delete a single media-query variant, leaving its image size in place."""
    return run_delete(backend, "contao:image-size-item:delete", item_id)
