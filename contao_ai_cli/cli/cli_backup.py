"""
backup group — Database backup management.
"""
import click

from contao_ai_cli.core import backup as backup_mod
from contao_ai_cli.core.status import cli_prefix
from .cli_health import _session_name
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
    """List existing backups, newest first: name, creation time, size in bytes."""
    b = _get_backend(ctx.obj.get("session"))
    result = backup_mod.backup_list(b)
    if as_json or ctx.obj.get("as_json") or result.get("status") != "ok":
        _output(result, as_json or ctx.obj.get("as_json"))
        if result.get("status") != "ok":
            ctx.exit(1)
        return
    if not result["backups"]:
        click.echo("No backups.")
    for entry in result["backups"]:
        click.echo(f"{entry['createdAt']}  {str(entry['size']):>12}  {entry['name']}")


@backup.command("restore")
@click.argument("backup_name")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def backup_restore(ctx, backup_name, as_json):
    """Restore a database backup, by a name `backup list` shows."""
    b = _get_backend(ctx.obj.get("session"))
    result = backup_mod.backup_restore(b, backup_name)
    if result.get("status") == "restored":
        # The search index still points at the pages of the state that was overwritten
        # (v1.10.0). Suggested, not run: emptying it is the operator's call.
        result["nextSteps"] = [{
            "command": f"{cli_prefix(_session_name(ctx.obj.get('session')))} contao automator purgeSearchTables",
            "optional": False,
            "reason": "The search index is not part of a backup: it still lists the pages of the "
                      "overwritten state, including pages that no longer exist. Purging it lets "
                      "Contao rebuild it from the restored site. The system log keeps its entries; "
                      "that is history, not a fault.",
        }]
    _output(result, as_json or ctx.obj.get("as_json"))
    if result.get("status") == "error":
        ctx.exit(1)
