"""
backup group — Database backup management.
"""
import click

from cli_anything.contao.core import backup as backup_mod
from .helpers import _get_backend, _output


@click.group()
def backup():
    """Database backup management."""


@backup.command("create")
@click.argument("name", default="")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def backup_create(ctx, name, as_json):
    """Create a database backup."""
    b = _get_backend(ctx.obj.get("session"))
    _output(backup_mod.backup_create(b, name), as_json or ctx.obj.get("as_json"))


@backup.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def backup_list(ctx, as_json):
    """List existing backups."""
    b = _get_backend(ctx.obj.get("session"))
    _output(backup_mod.backup_list(b), as_json or ctx.obj.get("as_json"))


@backup.command("restore")
@click.argument("backup_name")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def backup_restore(ctx, backup_name, as_json):
    """Restore a database backup."""
    b = _get_backend(ctx.obj.get("session"))
    _output(backup_mod.backup_restore(b, backup_name), as_json or ctx.obj.get("as_json"))
