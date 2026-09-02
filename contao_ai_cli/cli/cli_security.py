"""
security group — Security utilities.
"""
import click

from contao_ai_cli.core import security as security_mod
from .helpers import _get_backend, _output, resolve_password


@click.group()
def security():
    """Security utilities."""


@security.command("hash-password")
@click.argument("password", required=False)
@click.option("--password-stdin", is_flag=True,
              help="Read the password from stdin instead, so it stays out of the process list.")
@click.option("--algorithm", default="auto", show_default=True,
              help="Hashing algorithm (auto, bcrypt, argon2i, argon2id, sodium)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def security_hash_password(ctx, password, password_stdin, algorithm, as_json):
    """Hash a password using Symfony's password hasher.

    The password may be given as an argument — where the process list can read
    it — or piped in with --password-stdin, which is the safer form.
    """
    password = resolve_password(password, password_stdin, what="the PASSWORD argument")
    b = _get_backend(ctx.obj.get("session"))
    _output(security_mod.hash_password(b, password, algorithm),
            as_json or ctx.obj.get("as_json"))
