"""
self-update -- reinstall contao-ai-cli at the newest tag via pipx.

Measured on Windows 2026-09-17: works while another contao-ai-cli process is
running (pipx reuses the venv and overwrites the launcher). But pipx moves a
running launcher into its trash, and while that file stays locked every later
pipx call fails emptying the trash — so the result is read back from the new
launcher (Nr. 54), and a second self-update while an older contao-ai-cli window
is still open fails until that window is closed. Until v0.20.0 it was a
question inside `connect`; an agent could not reach it.
"""
import shutil

import click

from .helpers import CLI_INSTALL_URL, _output, check_cli_update, install_cli_update


@click.command("self-update")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def self_update(ctx, as_json):
    """Update contao-ai-cli to the newest release (pipx)."""
    as_json = as_json or (ctx.obj or {}).get("as_json")
    check = check_cli_update()

    def fail(message):
        _output({"status": "error", "code": 1, "current": check["current"], "message": message}, as_json)
        ctx.exit(1)

    if check["latest"] is None:
        fail("Could not reach GitHub to find the newest release. Nothing was changed.")
    if not check["update_available"]:
        _output({"status": "ok", "changed": False, "installed": check["current"],
                 "message": f"contao-ai-cli {check['current']} is up to date."}, as_json)
        return
    if shutil.which("pipx") is None:
        fail("pipx is not installed. Install it with: python -m pip install --user pipx && python -m pipx ensurepath")

    outcome = install_cli_update(check["latest"])
    if not outcome["updated"]:
        reason = f" pipx said: {outcome['reason']}" if outcome.get("reason") else ""
        fail(f"The update did not take effect (installed version reads {outcome['installed'] or 'nothing'}).{reason} "
             "On Windows, close other contao-ai-cli windows first. "
             f"Install it manually: pipx install --force git+{CLI_INSTALL_URL}@v{check['latest']}")
    _output({"status": "ok", "changed": True, "previous": check["current"], "installed": outcome["installed"],
             "message": "Updated. A running `contao-ai-cli repl` keeps the old code until it is restarted."}, as_json)
