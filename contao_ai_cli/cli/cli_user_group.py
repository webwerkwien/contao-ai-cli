"""
user-group group — Manage back end user groups (tl_user_group).
"""
import click

from contao_ai_cli.core import user_group as user_group_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group("user-group")
def user_group():
    """Manage back end user groups (tl_user_group) — the permission table."""
    pass


@user_group.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_group_list_cmd(ctx, as_json):
    """List all back end user groups."""
    _require_core_bundle(ctx, "user-group list")
    b = _get_backend(ctx.obj.get("session"))
    _output(user_group_mod.user_group_list(b), as_json or ctx.obj.get("as_json"))


@user_group.command("read")
@click.argument("group_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_group_read_cmd(ctx, group_id, as_json):
    """Read all fields of a group, permissions included."""
    _require_core_bundle(ctx, "user-group read")
    b = _get_backend(ctx.obj.get("session"))
    _output(user_group_mod.user_group_read(b, group_id), as_json or ctx.obj.get("as_json"))


@user_group.command("options")
@click.option("--table", default=None,
              help="Report cud and alexf for this table, e.g. tl_news")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_group_options_cmd(ctx, table, as_json):
    """List the accepted values for the permission fields.

    Read this before writing permissions. A wrong value does not fail — it is
    stored and simply never grants anything, so there is no error to learn from.
    """
    _require_core_bundle(ctx, "user-group options")
    b = _get_backend(ctx.obj.get("session"))
    _output(user_group_mod.user_group_options(b, table), as_json or ctx.obj.get("as_json"))


@user_group.command("create")
@click.option("--name", required=True, help="Group name shown in the back end")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Permission field, e.g. --set modules=page,article")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_group_create_cmd(ctx, name, fields, as_json):
    """Create a back end user group.

    Only the name is required; every permission defaults to "not granted".
    Lists are comma-separated: --set modules=page,article --set fop=f1,f2
    """
    _require_core_bundle(ctx, "user-group create")
    b = _get_backend(ctx.obj.get("session"))
    _output(user_group_mod.user_group_create(b, name, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@user_group.command("update")
@click.argument("group_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_group_update_cmd(ctx, group_id, ids, ids_from_file, fields, as_json):
    """Update a group, or many at once.

    A permission field is replaced, not extended: --set modules=page leaves the
    group with exactly one module. Read it first if you mean to add one.
    """
    _require_core_bundle(ctx, "user-group update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:user-group:update", group_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@user_group.command("delete")
@click.argument("group_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_group_delete_cmd(ctx, group_id, yes, as_json):
    """Delete a back end user group.

    Nothing is deleted with it, but every user in it loses what it granted —
    Contao leaves the dead ID in tl_user.groups rather than cleaning up.
    """
    _require_core_bundle(ctx, "user-group delete")
    if not confirm_delete(
        f"user group {group_id} — every back end user in it loses the permissions "
        f"it granted",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(user_group_mod.user_group_delete(b, group_id), as_json or ctx.obj.get("as_json"))
