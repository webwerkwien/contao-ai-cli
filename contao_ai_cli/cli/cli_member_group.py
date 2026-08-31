"""
member-group group — Manage front end member groups (tl_member_group).
"""
import click

from contao_ai_cli.core import member_group as member_group_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group("member-group")
def member_group():
    """Manage front end member groups (tl_member_group)."""
    pass


@member_group.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_group_list_cmd(ctx, as_json):
    """List all front end member groups."""
    _require_core_bundle(ctx, "member-group list")
    b = _get_backend(ctx.obj.get("session"))
    _output(member_group_mod.member_group_list(b), as_json or ctx.obj.get("as_json"))


@member_group.command("read")
@click.argument("group_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_group_read_cmd(ctx, group_id, as_json):
    """Read all fields of a member group."""
    _require_core_bundle(ctx, "member-group read")
    b = _get_backend(ctx.obj.get("session"))
    _output(member_group_mod.member_group_read(b, group_id), as_json or ctx.obj.get("as_json"))


@member_group.command("create")
@click.option("--name", required=True, help="Group name shown in the back end")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_group_create_cmd(ctx, name, fields, as_json):
    """Create a front end member group.

    --set redirect=1 needs --set jumpTo=<page id> alongside it: jumpTo is
    mandatory only once redirect opens its subpalette, and the command applies
    that rule the same way the back end does.
    """
    _require_core_bundle(ctx, "member-group create")
    b = _get_backend(ctx.obj.get("session"))
    _output(member_group_mod.member_group_create(b, name, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@member_group.command("update")
@click.argument("group_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_group_update_cmd(ctx, group_id, ids, ids_from_file, fields, as_json):
    """Update a member group, or many at once."""
    _require_core_bundle(ctx, "member-group update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:member-group:update", group_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@member_group.command("delete")
@click.argument("group_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_group_delete_cmd(ctx, group_id, yes, as_json):
    """Delete a front end member group.

    Protected content keeps pointing at the dead ID, so it stays protected with
    nobody able to reach it — check what references the group first.
    """
    _require_core_bundle(ctx, "member-group delete")
    if not confirm_delete(
        f"member group {group_id} — protected pages and elements keep pointing at it "
        f"and become unreachable for its members",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(member_group_mod.member_group_delete(b, group_id), as_json or ctx.obj.get("as_json"))
