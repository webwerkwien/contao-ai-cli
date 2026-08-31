"""Contao layout management (tl_layout)."""
import json
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    build_set_args, run_delete, run_json_or_raw, run_update,
)

#: What identifies a layout. `template` is in here because it decides whether
#: the layout is a legacy `fe_*` one or a modern Twig `page/layout` one, and
#: that changes what else about it means anything.
LIST_FIELDS = "id,pid,name,template"


def layout_list(backend: ContaoBackend, theme_id: int | None = None) -> dict:
    """List layouts, optionally only those of one theme."""
    cmd = (
        f"contao:record:list tl_layout --fields {shlex.quote(LIST_FIELDS)} "
        f"--order {shlex.quote('name ASC')}"
    )
    if theme_id is not None:
        cmd += f" --filter pid={int(theme_id)}"
    return run_json_or_raw(backend, cmd)


def layout_read(backend: ContaoBackend, layout_id: int) -> dict:
    """Read all fields of a tl_layout record."""
    cmd = f"contao:layout:read {layout_id}"
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def layout_create(backend: ContaoBackend, theme_id: int, name: str,
                  template: str, fields: dict | None = None) -> dict:
    """Create a page layout under a theme.

    `template` is required and has no default. Its options come from a callback
    that needs a live DataContainer — a legacy layout is offered the `fe_*` PHP
    template group, a modern one the `page/layout` Twig templates found on disk
    — so no create command can resolve the list. `fe_page` is the classic
    legacy value.

    A layout created this way has no sections and no modules. Both are wizard
    columns holding serialized structures, and a layout without modules renders
    nothing; fill them in afterwards.
    """
    cmd = (
        f"contao:layout:create --pid={int(theme_id)} --name={shlex.quote(name)} "
        f"--template={shlex.quote(template)} --no-interaction"
    )
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def layout_update(backend: ContaoBackend, layout_id: int, fields: dict) -> dict:
    """Update layout fields via contao-ai-core-bundle.

    `width`, `headerHeight`, `footerHeight`, `widthLeft` and `widthRight` are
    unit fields: pass a plain number and the server stores it with the record's
    existing unit, or `px` if it had none. Pass `--set width_unit=rem` alongside
    to change the unit itself.
    """
    return run_update(backend, "contao:layout:update", layout_id, fields)


def layout_delete(backend: ContaoBackend, layout_id: int) -> dict:
    """Delete a page layout.

    Nothing hangs below a layout. Pages referencing it are left alone and fall
    back to their parent's layout, which is Contao's own behaviour rather than
    anything arranged here.
    """
    return run_delete(backend, "contao:layout:delete", layout_id)
