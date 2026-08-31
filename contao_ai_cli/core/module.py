"""Contao front end modules (tl_module).

The largest table of the theme layer — 113 columns — and the one where "what do
I have to supply" has no single answer. Twelve fields carry `mandatory` in the
DCA, but a mandatory field only applies to the module types whose palette
contains it, which is exactly how `DC_Table` validates. A navigation needs
`pages`; a login module needs neither that nor anything else beyond a name.

Nothing here carries a table of that mapping. The server computes it from the
DCA at runtime, so module types from third-party extensions behave like core
ones without anyone adding them.
"""
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    build_set_args, run_delete, run_json_or_raw, run_update,
)

#: `type` is in here because it decides what the other 110 columns mean.
LIST_FIELDS = "id,pid,name,type"


def module_types(backend: ContaoBackend) -> dict:
    """List the module types this installation offers, with their requirements."""
    return run_json_or_raw(backend, "contao:module:types")


def module_list(backend: ContaoBackend, theme_id: int | None = None,
                module_type: str | None = None) -> dict:
    """List modules, optionally narrowed to one theme and/or one type."""
    cmd = (
        f"contao:record:list tl_module --fields {shlex.quote(LIST_FIELDS)} "
        f"--order {shlex.quote('name ASC')} --limit 100"
    )
    if theme_id is not None:
        cmd += f" --filter pid={int(theme_id)}"
    if module_type:
        cmd += f" --filter type={shlex.quote(module_type)}"
    return run_json_or_raw(backend, cmd)


def module_read(backend: ContaoBackend, module_id: int) -> dict:
    """Read every field of one tl_module record."""
    return run_json_or_raw(backend, f"contao:module:read {int(module_id)}")


def module_create(backend: ContaoBackend, theme_id: int, name: str,
                  module_type: str, fields: dict | None = None) -> dict:
    """Create a front end module under a theme.

    The server refuses a type it does not know — listing the ones it does — and
    refuses a type whose palette asks for fields that were not supplied, naming
    them. Run `module types` to see both up front.

    Multi-value fields take a comma-separated list: `news_archives=1,3`.
    """
    cmd = (
        f"contao:module:create --pid={int(theme_id)} --name={shlex.quote(name)} "
        f"--type={shlex.quote(module_type)} --no-interaction"
    )
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def module_update(backend: ContaoBackend, module_id: int, fields: dict) -> dict:
    """Update module fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:module:update", module_id, fields)


def module_delete(backend: ContaoBackend, module_id: int) -> dict:
    """Delete a front end module.

    Nothing hangs below a module. Layouts that place it are not touched: their
    `modules` column holds a serialized structure rather than a foreign key, and
    Contao skips a module it cannot find rather than failing.
    """
    return run_delete(backend, "contao:module:delete", module_id)
