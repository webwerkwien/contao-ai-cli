"""
user group — Backend user management.
"""
import click

from cli_anything.contao.core import session as session_mod, user as user_mod, dca_schema
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def user():
    """Backend user management."""


@user.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_list(ctx, as_json):
    """List backend users."""
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_list(b), as_json or ctx.obj.get("as_json"))


@user.command("create")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--name", required=True, help="Full name (required by Contao)")
@click.option("--email", required=True, help="E-mail address (required by Contao)")
@click.option("--language", default="en", show_default=True,
              help="Back end language, e.g. de, en (required by Contao)")
@click.option("--admin", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_create(ctx, username, password, name, email, language, admin, as_json):
    """Create a backend user."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE

    # DCA validation — runs only if schema has been synced, skipped otherwise
    missing = dca_schema.validate_fields(
        table='tl_user',
        provided={'username': username, 'password': password,
                  'name': name, 'email': email, 'language': language},
        session_path=session_path,
    )
    if missing:
        schema = dca_schema.load_schema('tl_user', session_path)
        details = []
        for f in missing:
            fdef = schema['fields'].get(f, {})
            label = fdef.get('label') or f
            details.append(f"--{f} ({label})")
        raise click.UsageError(
            f"Missing mandatory field(s) for tl_user: {', '.join(details)}\n"
            f"Run 'schema sync tl_user' to refresh the field list."
        )

    b = _get_backend(session_path)
    _output(user_mod.user_create(b, username, password, name, email, language, admin),
            as_json or ctx.obj.get("as_json"))


@user.command("password")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_password(ctx, username, password, as_json):
    """Change a user's password."""
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_password(b, username, password),
            as_json or ctx.obj.get("as_json"))


@user.command("update")
@click.argument("username")
@click.option("--field", "fields", multiple=True,
              metavar="FIELD=VALUE", help="Field to update, e.g. --field email=new@example.com")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_update(ctx, username, fields, as_json):
    """Update a backend user field via contao-cli-bridge."""
    _require_bridge(ctx, "user update")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_update(b, username, parsed), as_json or ctx.obj.get("as_json"))


@user.command("delete")
@click.argument("username")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_delete(ctx, username, as_json):
    """Delete a backend user via contao-cli-bridge."""
    _require_bridge(ctx, "user delete")
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_delete(b, username), as_json or ctx.obj.get("as_json"))
