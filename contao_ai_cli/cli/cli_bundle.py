"""
bundle group -- install or update contao-ai-core-bundle / contao-ai-backend-bundle.

Until v0.20.0 this lived inside the `connect` wizard as yes/no questions, so an agent
could not reach it at all (2026-09-17).
"""
import click

from contao_ai_cli.core import bundles as bundles_mod, session as session_mod
from .helpers import _get_backend, _output


def _run(ctx, name, action, allow_plugins, as_json):
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    result = bundles_mod.install_bundle(_get_backend(session_path), name, action, allow_plugins)
    if name == "core" and result["status"] == "ok":
        cfg = session_mod.load_session(session_path)
        cfg["core_bundle_available"] = True
        session_mod.save_session(cfg, session_path)
    _output(result, as_json or ctx.obj.get("as_json"))
    if result["status"] == "error":
        ctx.exit(1)


@click.group()
def bundle():
    """Install or update the contao-ai bundles on the connected site."""


@bundle.command("install")
@click.argument("name", type=click.Choice(sorted(bundles_mod.BUNDLES)))
@click.option("--allow-plugins", is_flag=True,
              help="Without a Contao Manager: write the needed allow-plugins into composer.json")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def bundle_install(ctx, name, allow_plugins, as_json):
    """Install a bundle (core or backend) with Composer or the Contao Manager."""
    _run(ctx, name, "install", allow_plugins, as_json)


@bundle.command("update")
@click.argument("name", type=click.Choice(sorted(bundles_mod.BUNDLES)))
@click.option("--allow-plugins", is_flag=True,
              help="Without a Contao Manager: write the needed allow-plugins into composer.json")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def bundle_update(ctx, name, allow_plugins, as_json):
    """Update a bundle (core or backend) to its newest release."""
    _run(ctx, name, "update", allow_plugins, as_json)
