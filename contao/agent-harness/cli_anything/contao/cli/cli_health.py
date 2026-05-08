"""
health command — show update status for the CLI itself, the core-bundle on
the connected server, and the bridge configuration. Read-only; reports only.

Use `contao-ai-cli connect` (re-connect) when you actually want to install
updates — `health` is a passive view to decide whether you need to.
"""
import click

from cli_anything.contao.core import (
    backend_bridge as bridge_mod,
    session as session_mod,
)
from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from .helpers import (
    check_cli_update,
    get_core_bundle_installed_version,
    get_core_bundle_latest_version,
    _output,
)


@click.command()
@click.pass_context
def health(ctx):
    """Show CLI, core-bundle and bridge status (read-only)."""
    as_json = ctx.obj.get("as_json")

    # ── CLI self-update check ────────────────────────────────────────────────
    cli_update = check_cli_update()
    cli_status = {
        "installed": cli_update["current"],
        "latest":    cli_update["latest"],
        "up_to_date": not cli_update["update_available"],
    }

    # ── Core-bundle check (needs an active session) ──────────────────────────
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    core_status: dict = {"reachable": False}
    # Use ContaoBackend.from_session directly instead of _get_backend so a
    # missing/incomplete session doesn't sys.exit() — health should report
    # CLI + bridge status even without an active SSH session.
    try:
        backend = ContaoBackend.from_session(session_path)
        installed = get_core_bundle_installed_version(backend)
        latest    = get_core_bundle_latest_version()
        core_status = {
            "reachable":  True,
            "installed":  installed,
            "latest":     latest,
            "up_to_date": (
                installed is not None
                and latest is not None
                and installed.lstrip("v") == latest.lstrip("v")
            ),
        }
    except ContaoBackendError as e:
        core_status = {"reachable": False, "reason": f"no active session ({e})"}
    except Exception as e:
        core_status = {"reachable": False, "reason": str(e)}

    # ── Bridge configuration ─────────────────────────────────────────────────
    cfg = session_mod.load_session(session_path)
    bridge_status: dict
    if cfg.get("bridge_url") and cfg.get("bridge_token"):
        bridge_status = {
            "configured": True,
            "url":        cfg["bridge_url"],
            "token":      bridge_mod.mask_token(cfg["bridge_token"]),
        }
    else:
        bridge_status = {"configured": False}

    result = {
        "cli":    cli_status,
        "core":   core_status,
        "bridge": bridge_status,
    }

    if as_json:
        _output(result, True)
        return

    # Pretty text output
    click.echo()
    click.echo(click.style("contao-ai-cli health", bold=True))
    # ASCII separator — Unicode box-drawing chars (─) blow up under
    # Windows cp1252 default console encoding.
    click.echo("-" * 50)

    cli_color = "green" if cli_status["up_to_date"] else "yellow"
    cli_msg = f"  CLI       v{cli_status['installed']}"
    if not cli_status["up_to_date"] and cli_status["latest"]:
        cli_msg += f"   → update available: v{cli_status['latest']}"
    elif cli_status["latest"] is None:
        cli_msg += "   (could not reach GitHub)"
    else:
        cli_msg += "   up to date"
    click.echo(click.style(cli_msg, fg=cli_color))

    if not core_status["reachable"]:
        reason = core_status.get("reason", "unreachable")
        click.echo(click.style(f"  Core      unreachable ({reason})", fg="red"))
    elif core_status.get("installed") is None:
        click.echo(click.style("  Core      not installed", fg="yellow"))
    else:
        installed = core_status["installed"]
        latest    = core_status.get("latest")
        if installed.startswith("dev-"):
            click.echo(f"  Core      {installed}   (development version, no update check)")
        elif core_status.get("up_to_date"):
            click.echo(click.style(f"  Core      {installed}   up to date", fg="green"))
        elif latest:
            click.echo(click.style(
                f"  Core      {installed}   → update available: v{latest}",
                fg="yellow",
            ))
        else:
            click.echo(f"  Core      {installed}   (could not reach Packagist)")

    if bridge_status["configured"]:
        click.echo(click.style(
            f"  Bridge    configured: {bridge_status['url']}   token: {bridge_status['token']}",
            fg="green",
        ))
    else:
        click.echo(click.style("  Bridge    not configured", fg="yellow"))

    click.echo()
    if not cli_status["up_to_date"] or (
        core_status.get("reachable")
        and core_status.get("installed") is not None
        and not core_status.get("up_to_date")
        and not (core_status.get("installed") or "").startswith("dev-")
    ):
        click.echo(click.style(
            "  Tipp: 'contao-ai-cli connect ...' (Re-Connect) installiert verfügbare Updates.",
            fg="cyan",
        ))
