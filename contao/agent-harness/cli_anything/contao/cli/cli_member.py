"""
member group — Manage Contao frontend members (tl_member).
"""
import click

from cli_anything.contao.core import session as session_mod, member as member_mod, dca_schema
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def member():
    """Manage Contao frontend members (tl_member)."""
    pass


@member.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_list_cmd(ctx, as_json):
    """List all frontend members."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(member_mod.member_list(b), as_json or ctx.obj.get("as_json"))


@member.command("create")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--firstname", required=True)
@click.option("--lastname", required=True)
@click.option("--email", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_create_cmd(ctx, username, password, firstname, lastname, email, as_json):
    """Create a new frontend member."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    missing = dca_schema.validate_fields(
        'tl_member',
        {'username': username, 'password': password,
         'firstname': firstname, 'lastname': lastname, 'email': email},
        session_path
    )
    if missing:
        schema = dca_schema.load_schema('tl_member', session_path)
        if schema:
            details = [f"--{f} ({schema['fields'][f].get('label') or f})" for f in missing]
        else:
            details = [f"--{f}" for f in missing]
        raise click.UsageError(f"Missing mandatory field(s) for tl_member: {', '.join(details)}")
    b = _get_backend(session_path)
    _output(member_mod.member_create(b, username, password, firstname, lastname, email),
            as_json or ctx.obj.get("as_json"))


@member.command("update")
@click.argument("username")
@click.option("--field", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_update(ctx, username, fields, as_json):
    """Update a frontend member field via contao-ai-core-bundle."""
    _require_bridge(ctx, "member update")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(member_mod.member_update(b, username, parsed), as_json or ctx.obj.get("as_json"))


@member.command("delete")
@click.argument("username")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_delete(ctx, username, as_json):
    """Delete a frontend member via contao-ai-core-bundle."""
    _require_bridge(ctx, "member delete")
    b = _get_backend(ctx.obj.get("session"))
    _output(member_mod.member_delete(b, username), as_json or ctx.obj.get("as_json"))
