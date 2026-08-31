"""Front end member groups (tl_member_group).

The counterpart to `tl_user_group` on the public side: this is what the
`groups` field of a protected page, article or content element points at, and
what a member is assigned to.

Six fields, only `name` required — with one wrinkle. `jumpTo` is mandatory in
the DCA but lives in a subpalette, so Contao demands it only once `redirect` is
switched on. The bundle applies the same rule:

    member-group create --name "Members"                          → ok
    member-group create --name "Members" --set redirect=1         → rejected
    member-group create --name "Members" --set redirect=1 \\
                        --set jumpTo=7                            → ok
"""
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    build_set_args, run_delete, run_json_or_raw, run_update,
)

LIST_FIELDS = "id,name,redirect,jumpTo,disable,tstamp"


def member_group_list(backend: ContaoBackend) -> dict:
    """List all front end member groups."""
    return run_json_or_raw(
        backend,
        f"contao:record:list tl_member_group --fields {shlex.quote(LIST_FIELDS)} "
        f"--order {shlex.quote('name ASC')}",
    )


def member_group_read(backend: ContaoBackend, group_id: int) -> dict:
    """Read every field of one tl_member_group record."""
    return run_json_or_raw(backend, f"contao:member-group:read {int(group_id)}")


def member_group_create(backend: ContaoBackend, name: str,
                        fields: dict | None = None) -> dict:
    """Create a front end member group.

    Rejects `redirect=1` without a `jumpTo`, because that is what DC_Table does
    once the subpalette is open.
    """
    cmd = f"contao:member-group:create --name={shlex.quote(name)} --no-interaction"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def member_group_update(backend: ContaoBackend, group_id: int, fields: dict) -> dict:
    """Update a front end member group."""
    return run_update(backend, "contao:member-group:update", group_id, fields)


def member_group_delete(backend: ContaoBackend, group_id: int) -> dict:
    """Delete a front end member group.

    No cascade, and the references survive: `tl_member.groups` and every
    `groups` field on protected content keep the dead ID. Protected content
    stays protected with nobody in the group — the safe direction to fail in.
    """
    return run_delete(backend, "contao:member-group:delete", group_id)
