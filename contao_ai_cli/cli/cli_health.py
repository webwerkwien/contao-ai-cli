"""
health command — show update status for the CLI itself, the core-bundle on
the connected server, and the bridge. Read-only; reports only.

To install updates use `contao-ai-cli self-update` and `contao-ai-cli bundle update`
(since v0.21.0; before, a re-connect ran a wizard) — `health` is a passive view to
decide whether you need to.

The bridge line reports three states rather than two, because "not configured"
used to cover both a missing contao-ai-backend-bundle and a present one without
a token, and the two need opposite next steps.
"""
import click

from contao_ai_cli.core import session as session_mod
from contao_ai_cli.core.status import _bridge_state, collect_status  # noqa: F401 - _bridge_state kept importable here for test_health.py
from .helpers import BACKEND_BUNDLE, _output


@click.command()
@click.pass_context
def health(ctx):
    """Show CLI, core-bundle and bridge status (read-only)."""
    as_json = ctx.obj.get("as_json")

    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    result = collect_status(session_path)
    cli_status, contao_status = result["cli"], result["contao"]
    core_status, bridge_status = result["core"], result["bridge"]

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

    # The Contao our three parts sit on. Stated plainly, without a verdict —
    # see the CONTAO_CORE_BUNDLE note in helpers.py.
    if contao_status["installed"] is None:
        click.echo(click.style("  Contao    unknown (could not read composer)", fg="yellow"))
    else:
        click.echo(f"  Contao    {contao_status['installed']}")

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
        elif latest and core_status.get("update_available"):
            click.echo(click.style(
                f"  Core      {installed}   -> update available: v{latest}",
                fg="yellow",
            ))
        else:
            click.echo(f"  Core      {installed}   (could not reach Packagist)")

    # Not an update line: it answers "how would I install something this CLI does
    # not manage" before anyone has to guess it. See status.collect_status.
    composer_status = result["composer"]
    if composer_status["via"] == "contao-manager":
        click.echo(f"  Composer  via Contao Manager: {composer_status['command']}")
    elif composer_status["via"] == "composer":
        click.echo("  Composer  plain composer (no Contao Manager found)")

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
        and core_status.get("update_available")
        and not (core_status.get("installed") or "").startswith("dev-")
    ):
        # ASCII only — non-ASCII chars get mangled into ? on Windows cp1252 stdout.
        click.echo(click.style(
            "  Tip: 'contao-ai-cli self-update' / 'contao-ai-cli bundle update core' install updates.",
            fg="cyan",
        ))
