"""
member group — Manage Contao frontend members (tl_member).
"""
import click

from contao_ai_cli.core import session as session_mod, member as member_mod, dca_schema
from .helpers import (
    _get_backend, _output, _require_core_bundle, parse_set_fields, resolve_password,
)


@click.group()
def member():
    """Manage Contao frontend members (tl_member)."""
    pass


@member.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def member_list_cmd(ctx, as_json, limit, offset):
    """List all frontend members."""
    _require_core_bundle(ctx, "member list")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(member_mod.member_list(b, limit, offset), as_json or ctx.obj.get("as_json"))


@member.command("create")
@click.option("--username", required=True)
@click.option("--password", default=None,
              help="The password. Visible in the process list — prefer --password-stdin.")
@click.option("--password-stdin", is_flag=True,
              help="Read the password from stdin instead, so it stays out of the process list.")
@click.option("--firstname", required=True)
@click.option("--lastname", required=True)
@click.option("--email", required=True)
@click.option("--set", "set_fields", multiple=True, metavar="FIELD=VALUE",
              help="Further fields, as member update takes them, e.g. --set groups=1,2")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_create_cmd(ctx, username, password, password_stdin, firstname, lastname, email, set_fields, as_json):
    """Create a front end member (core-bundle v0.26.0; the password reaches the server on stdin)."""
    _require_core_bundle(ctx, "member create")
    password = resolve_password(password, password_stdin)
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
    _output(member_mod.member_create(b, username, password, firstname, lastname, email,
                                     parse_set_fields(set_fields)),
            as_json or ctx.obj.get("as_json"))


@member.command("password")
@click.option("--username", required=True)
@click.option("--password", default=None,
              help="The new password. Visible in the process list — prefer --password-stdin.")
@click.option("--password-stdin", is_flag=True,
              help="Read the password from stdin instead, so it stays out of the process list.")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_password_cmd(ctx, username, password, password_stdin, as_json):
    """Set a front end member's password (core-bundle v0.26.0) — `member update` refuses it."""
    _require_core_bundle(ctx, "member password")
    password = resolve_password(password, password_stdin)
    b = _get_backend(ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE)
    _output(member_mod.member_password(b, username, password), as_json or ctx.obj.get("as_json"))


@member.command("update")
@click.argument("username")
# `--set` like every other update command; `--field` was this one's own spelling until
# v0.27.0 and still works (agent test before 1.0, 2026-09-18).
@click.option("--set", "--field", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_update(ctx, username, fields, as_json):
    """Update a frontend member field via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "member update")
    parsed = parse_set_fields(fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(member_mod.member_update(b, username, parsed), as_json or ctx.obj.get("as_json"))


@member.command("delete")
@click.argument("username")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_delete(ctx, username, as_json):
    """Delete a frontend member via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "member delete")
    b = _get_backend(ctx.obj.get("session"))
    _output(member_mod.member_delete(b, username), as_json or ctx.obj.get("as_json"))
