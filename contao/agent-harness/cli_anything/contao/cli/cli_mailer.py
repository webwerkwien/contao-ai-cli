"""
mailer group — Mailer operations.
"""
import click

from cli_anything.contao.core import mailer as mailer_mod
from .helpers import _get_backend, _output


@click.group()
def mailer():
    """Mailer operations."""


@mailer.command("test")
@click.option("--to", required=True, help="Recipient e-mail address")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def mailer_test(ctx, to, as_json):
    """Send a test e-mail to verify mailer configuration."""
    b = _get_backend(ctx.obj.get("session"))
    _output(mailer_mod.mailer_test(b, to), as_json or ctx.obj.get("as_json"))
