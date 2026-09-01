"""
listing group — Manage Contao listing modules (contao/listing-bundle).
"""
import click

from contao_ai_cli.core import session as session_mod, listing as listing_mod
from .helpers import _require_core_bundle, _get_backend, _output


@click.group()
def listing():
    """Manage Contao listing modules (contao/listing-bundle)."""
    pass


@listing.command("modules")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def listing_modules(ctx, limit, offset):
    """List all configured listing modules."""
    _require_core_bundle(ctx, "listing modules")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(listing_mod.listing_module_list(b, limit, offset), ctx.obj.get("as_json"))


@listing.command("data")
@click.argument("module_id", type=int)
@click.pass_context
def listing_data_cmd(ctx, module_id):
    """Fetch listing data for a specific module ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(listing_mod.listing_data(b, module_id), ctx.obj.get("as_json"))


@listing.command("config")
@click.argument("module_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def listing_config_cmd(ctx, module_id, as_json):
    """The configuration of one listing module, read through the server."""
    _require_core_bundle(ctx, "listing config")
    b = _get_backend(ctx.obj.get("session"))
    _output(listing_mod.listing_config(b, module_id), as_json or ctx.obj.get("as_json"))
