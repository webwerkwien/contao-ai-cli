"""
bundle group -- install or update contao-ai-core-bundle / contao-ai-backend-bundle.

Until v0.20.0 this lived inside the `connect` wizard as yes/no questions, so an agent
could not reach it at all (2026-09-17).
"""
import click

from contao_ai_cli.core import bundles as bundles_mod, session as session_mod
from .helpers import _get_backend, _output


def _resolve(name: str) -> str:
    """Accept `core`/`backend`, and point anything else somewhere useful.

    `click.Choice` used to do this, and answered `invalid choice: changelanguage`.
    That is a wall where a signpost belongs (issue #57): the group is called
    `bundle`, which reads as "any bundle", and a caller who wanted an extension
    installed learns only that this is not the way -- not what is.
    """
    if name in bundles_mod.BUNDLES:
        return name
    # A full package name for one of ours is an obvious thing to try.
    for short, package in bundles_mod.BUNDLES.items():
        if name == package:
            return short
    raise click.UsageError(
        f"`bundle install {name}` -- this command manages the two contao-ai bundles only "
        f"({', '.join(sorted(bundles_mod.BUNDLES))}), because it knows their version "
        f"constraints and reads the installed version back afterwards. It knows none of "
        f"that for another package.\n\n"
        f"To install any other extension, use the Contao Manager's Composer passthrough "
        f"over the same SSH connection -- a dry run first:\n\n"
        f"    php public/contao-manager.phar.php composer require {name} --dry-run\n"
        f"    php public/contao-manager.phar.php composer require {name}\n\n"
        f"`contao-ai-cli health --json` reports the exact command for the connected site "
        f"under `composer.command`. Afterwards, if the extension adds DCA fields, refresh "
        f"the cached schema: contao-ai-cli schema sync <table>."
    )


def _run(ctx, name, action, allow_plugins, as_json):
    name = _resolve(name)
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
@click.argument("name", metavar="[core|backend]")
@click.option("--allow-plugins", is_flag=True,
              help="Without a Contao Manager: write the needed allow-plugins into composer.json")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def bundle_install(ctx, name, allow_plugins, as_json):
    """Install a bundle (core or backend) with Composer or the Contao Manager."""
    _run(ctx, name, "install", allow_plugins, as_json)


@bundle.command("update")
@click.argument("name", metavar="[core|backend]")
@click.option("--allow-plugins", is_flag=True,
              help="Without a Contao Manager: write the needed allow-plugins into composer.json")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def bundle_update(ctx, name, allow_plugins, as_json):
    """Update a bundle (core or backend) to its newest release."""
    _run(ctx, name, "update", allow_plugins, as_json)
