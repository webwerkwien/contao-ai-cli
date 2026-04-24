"""
listing group — Manage Contao listing modules (contao/listing-bundle).
"""
import click

from cli_anything.contao.core import session as session_mod, listing as listing_mod
from .helpers import _get_backend, _output


@click.group()
def listing():
    """Manage Contao listing modules (contao/listing-bundle)."""
    pass


@listing.command("modules")
@click.pass_context
def listing_modules(ctx):
    """List all configured listing modules."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(listing_mod.listing_module_list(b), ctx.obj.get("as_json"))


@listing.command("data")
@click.argument("module_id", type=int)
@click.pass_context
def listing_data_cmd(ctx, module_id):
    """Fetch listing data for a specific module ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(listing_mod.listing_data(b, module_id), ctx.obj.get("as_json"))
