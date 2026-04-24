"""
version group — Contao version history management (tl_version).
"""
import click

from cli_anything.contao.core import version as version_mod
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def version():
    """Contao version history management (tl_version)."""
    pass


@version.command("list")
@click.option("--table", required=True, help="Table name, e.g. tl_content")
@click.option("--id",    "record_id", type=int, required=True, help="Record ID")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def version_list_cmd(ctx, table, record_id, as_json):
    """List all version snapshots for a record."""
    _require_bridge(ctx, "version list")
    b = _get_backend(ctx.obj.get("session"))
    _output(version_mod.version_list(b, table, record_id), as_json or ctx.obj.get("as_json"))


@version.command("read")
@click.option("--table",   required=True, help="Table name, e.g. tl_content")
@click.option("--id",      "record_id", type=int, required=True, help="Record ID")
@click.option("--version", "ver", type=int, required=True, help="Version number")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def version_read_cmd(ctx, table, record_id, ver, as_json):
    """Read a specific version snapshot (data field deserialized)."""
    _require_bridge(ctx, "version read")
    b = _get_backend(ctx.obj.get("session"))
    _output(version_mod.version_read(b, table, record_id, ver), as_json or ctx.obj.get("as_json"))


@version.command("restore")
@click.option("--table",   required=True, help="Table name, e.g. tl_content")
@click.option("--id",      "record_id", type=int, required=True, help="Record ID")
@click.option("--version", "ver", type=int, required=True, help="Version number to restore")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def version_restore_cmd(ctx, table, record_id, ver, as_json):
    """Restore a record to a specific version."""
    _require_bridge(ctx, "version restore")
    b = _get_backend(ctx.obj.get("session"))
    _output(version_mod.version_restore(b, table, record_id, ver), as_json or ctx.obj.get("as_json"))


@version.command("create")
@click.option("--table", required=True, help="Table name, e.g. tl_content")
@click.option("--id",    "record_id", type=int, required=True, help="Record ID")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def version_create_cmd(ctx, table, record_id, as_json):
    """Manually create a version snapshot for a record."""
    _require_bridge(ctx, "version create")
    b = _get_backend(ctx.obj.get("session"))
    _output(version_mod.version_create(b, table, record_id), as_json or ctx.obj.get("as_json"))
