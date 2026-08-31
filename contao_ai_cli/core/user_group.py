"""Back end user groups (tl_user_group) — the permission table.

This is where a Contao editor's world is defined: which back end modules they
see, which branches of the page tree and which folders they reach, which fields
they may edit, which tables they may create and delete in. A back end user
without a group can log in and do close to nothing.

Every permission field is a list, stored serialized. The bundle converts a
comma-separated value from the DCA, including the binary UUIDs `filemounts`
needs and including `cud`, whose widget stores a list without declaring
`multiple` — so the CLI passes values through as the user typed them.

⚠️ Updating a permission field **replaces** it. Passing `modules=page` to a
group that had five modules leaves it with one. Read first, then write the full
list you want the group to end with.
"""
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    build_set_args, run_delete, run_json_or_raw, run_update,
)

#: `tl_user_group` has seventeen columns and most of them are long serialized
#: blobs. These four identify a group; the rest is what `read` is for.
LIST_FIELDS = "id,name,disable,tstamp"


def user_group_list(backend: ContaoBackend) -> dict:
    """List all back end user groups."""
    return run_json_or_raw(
        backend,
        f"contao:record:list tl_user_group --fields {shlex.quote(LIST_FIELDS)} "
        f"--order {shlex.quote('name ASC')}",
    )


def user_group_read(backend: ContaoBackend, group_id: int) -> dict:
    """Read every field of one tl_user_group record, permissions included."""
    return run_json_or_raw(backend, f"contao:user-group:read {int(group_id)}")


def user_group_create(backend: ContaoBackend, name: str,
                      fields: dict | None = None) -> dict:
    """Create a back end user group.

    Only the name is required, which mirrors the DCA: every permission field
    defaults to "not granted". A group with nothing but a name is valid and
    harmless — the right default for a permission record.
    """
    cmd = f"contao:user-group:create --name={shlex.quote(name)} --no-interaction"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def user_group_update(backend: ContaoBackend, group_id: int, fields: dict) -> dict:
    """Update a back end user group. Multi-value fields are replaced, not merged."""
    return run_update(backend, "contao:user-group:update", group_id, fields)


def user_group_delete(backend: ContaoBackend, group_id: int) -> dict:
    """Delete a back end user group.

    No cascade — `tl_user_group` declares no child tables. What stays behind is
    a dangling reference: `tl_user.groups` keeps the dead ID, and Contao does
    not clean that up in the back end either. The users remain, they just lose
    what this group granted.
    """
    return run_delete(backend, "contao:user-group:delete", group_id)


def user_group_options(backend: ContaoBackend, table: str | None = None) -> dict:
    """Accepted values for the permission fields.

    Worth reaching for before every write to this table. A wrong value does not
    fail: it is stored, and the permission is simply never granted. There is no
    error to read, so guessing does not even self-correct here.

    Without `table` this returns the install-wide sets — back end modules,
    content elements, page types, file operations. With one it returns the two
    per-table sets, `cud` and `alexf`, for that table.
    """
    cmd = "contao:user-group:options"
    if table:
        cmd += f" --table={shlex.quote(table)}"
    return run_json_or_raw(backend, cmd)
