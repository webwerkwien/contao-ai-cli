"""Contao themes (tl_theme) — the root of the theme layer.

A theme owns the modules, layouts and image sizes beneath it. Deleting one
therefore takes all of them with it, which is why the CLI wrapper spells the
child tables out before asking.
"""
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    build_set_args, run_delete, run_json_or_raw, run_update,
)

#: A theme has seven columns; these are the ones that identify it. `templates`
#: is the template subfolder, which is what usually distinguishes two themes on
#: the same install.
LIST_FIELDS = "id,name,author,templates"


def theme_list(backend: ContaoBackend) -> dict:
    """List all themes."""
    return run_json_or_raw(
        backend,
        f"contao:record:list tl_theme --fields {shlex.quote(LIST_FIELDS)} "
        f"--order {shlex.quote('name ASC')}",
    )


def theme_read(backend: ContaoBackend, theme_id: int) -> dict:
    """Read every field of one tl_theme record."""
    return run_json_or_raw(backend, f"contao:theme:read {int(theme_id)}")


def theme_create(backend: ContaoBackend, name: str, author: str,
                 fields: dict | None = None) -> dict:
    """Create a theme.

    `author` is a free-text credit line, not a user reference — Contao's own
    demo theme carries a list of names in that column.
    """
    cmd = (
        f"contao:theme:create --name={shlex.quote(name)} "
        f"--author={shlex.quote(author)} --no-interaction"
    )
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def theme_update(backend: ContaoBackend, theme_id: int, fields: dict) -> dict:
    """Update theme fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:theme:update", theme_id, fields)


def theme_delete(backend: ContaoBackend, theme_id: int) -> dict:
    """Delete a theme with everything under it.

    The widest cascade in the bundle: `tl_theme.ctable` names `tl_module`,
    `tl_layout`, `tl_image_size` and `tl_content`, and the collector recurses,
    so image size variants come along underneath. Restorable from the back
    end's "Restore" module as one entry.
    """
    return run_delete(backend, "contao:theme:delete", theme_id)
