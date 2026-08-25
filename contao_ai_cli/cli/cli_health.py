"""
health command — show update status for the CLI itself, the core-bundle on
the connected server, and the bridge. Read-only; reports only.

Use `contao-ai-cli connect` (re-connect) when you actually want to install
updates — `health` is a passive view to decide whether you need to.

The bridge line reports three states rather than two, because "not configured"
used to cover both a missing contao-ai-backend-bundle and a present one without
a token, and the two need opposite next steps.
"""
import click

from contao_ai_cli.core import (
    backend_bridge as bridge_mod,
    session as session_mod,
)
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from .helpers import (
    BACKEND_BUNDLE,
    CORE_BUNDLE,
    check_cli_update,
    get_core_bundle_latest_version,
    get_installed_package_versions,
    _output,
)


def _bridge_state(installed: bool | None, configured: bool) -> str:
    """
    Boil "is the bundle there" and "does the session have a token" down to one word.

    Two separate conditions used to collapse into one message: `health` reported
    "not configured" whether the bundle was missing or merely keyless. That reads
    like "installed, needs a key" and sends you off to set a key that has nothing
    to install it into. So a missing bundle outranks everything, including a
    session that does carry a token - that combination is a real misconfiguration
    and worth saying out loud rather than hiding behind "ready".
    """
    if installed is False:
        return "not_installed"
    if configured:
        return "ready"
    if installed is True:
        return "not_configured"
    return "unknown"


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
    # None = could not look, which is not the same as "not installed".
    backend_bundle_installed: bool | None = None
    # Use ContaoBackend.from_session directly instead of _get_backend so a
    # missing/incomplete session doesn't sys.exit() — health should report
    # CLI + bridge status even without an active SSH session.
    try:
        backend = ContaoBackend.from_session(session_path)
        # Both bundles in one round-trip; they live in the same installed.json.
        versions  = get_installed_package_versions(backend, [CORE_BUNDLE, BACKEND_BUNDLE])
        installed = versions[CORE_BUNDLE]
        backend_bundle_installed = versions[BACKEND_BUNDLE] is not None
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

    # ── Bridge: installed on the server, and configured in the session ───────
    cfg = session_mod.load_session(session_path)
    configured = bool(cfg.get("bridge_url") and cfg.get("bridge_token"))
    bridge_status = {
        "state":      _bridge_state(backend_bundle_installed, configured),
        "installed":  backend_bundle_installed,
        "configured": configured,
    }
    if configured:
        bridge_status["url"]   = cfg["bridge_url"]
        bridge_status["token"] = bridge_mod.mask_token(cfg["bridge_token"])

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
        cli_msg += f"   -> update available: v{cli_status['latest']}"
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
                f"  Core      {installed}   -> update available: v{latest}",
                fg="yellow",
            ))
        else:
            click.echo(f"  Core      {installed}   (could not reach Packagist)")

    state = bridge_status["state"]
    if state == "ready":
        line = f"  Bridge    ready: {bridge_status['url']}   token: {bridge_status['token']}"
        if bridge_status["installed"] is None:
            line += "   (server not reached, install state unverified)"
        click.echo(click.style(line, fg="green"))
    elif state == "not_installed":
        click.echo(click.style(
            f"  Bridge    not installed ({BACKEND_BUNDLE})", fg="yellow",
        ))
        if bridge_status["configured"]:
            click.echo(click.style(
                "            this session has a bridge token, but there is nothing on the "
                "server to answer it", fg="red",
            ))
    elif state == "not_configured":
        click.echo(click.style(
            "  Bridge    installed, not configured"
            "   -> contao-ai-cli bridge configure --url ... --token ...", fg="yellow",
        ))
    else:
        click.echo(click.style(
            "  Bridge    not configured   (server not reached, install state unknown)",
            fg="yellow",
        ))

    click.echo()
    if not cli_status["up_to_date"] or (
        core_status.get("reachable")
        and core_status.get("installed") is not None
        and not core_status.get("up_to_date")
        and not (core_status.get("installed") or "").startswith("dev-")
    ):
        # ASCII only — non-ASCII chars get mangled into ? on Windows cp1252 stdout.
        click.echo(click.style(
            "  Tip: re-run 'contao-ai-cli connect ...' to install available updates.",
            fg="cyan",
        ))
