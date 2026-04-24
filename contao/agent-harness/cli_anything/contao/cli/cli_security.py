"""
security group — Security utilities.
"""
import click

from cli_anything.contao.core import security as security_mod
from .helpers import _get_backend, _output


@click.group()
def security():
    """Security utilities."""


@security.command("hash-password")
@click.argument("password")
@click.option("--algorithm", default="auto", show_default=True,
              help="Hashing algorithm (auto, bcrypt, argon2i, argon2id, sodium)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def security_hash_password(ctx, password, algorithm, as_json):
    """Hash a password using Symfony's password hasher."""
    b = _get_backend(ctx.obj.get("session"))
    _output(security_mod.hash_password(b, password, algorithm),
            as_json or ctx.obj.get("as_json"))
