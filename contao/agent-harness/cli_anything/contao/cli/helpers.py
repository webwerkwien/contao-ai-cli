"""
Shared helpers for the contao-cli-agent CLI modules.
"""
import json
import sys
import click

from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.utils.repl_skin import ReplSkin
from cli_anything.contao.core import session as session_mod

__version__ = "1.0.0"

skin = ReplSkin("contao", version=__version__)


def _get_backend(session_path=None):
    path = session_path or session_mod.DEFAULT_SESSION_FILE
    try:
        return ContaoBackend.from_session(path)
    except ContaoBackendError as e:
        click.echo(click.style(f"[ERROR] {e}", fg="red"), err=True)
        sys.exit(1)


def _output(data, as_json=False):
    if as_json:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, dict) and "output" in data:
            click.echo(data["output"])
        elif isinstance(data, (list, dict)):
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            click.echo(str(data))


def _detect_bridge(backend) -> bool:
    """Check if contao-cli-bridge commands are available on the server."""
    try:
        result = backend.run("list")
        return "contao:user:update" in result["stdout"]
    except Exception:
        return False


def _require_bridge(ctx, command_name: str):
    """Raise UsageError with install hint if bridge is not available."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    try:
        with open(session_path) as f:
            cfg = json.load(f)
        bridge_available = cfg.get("bridge_available", False)
    except Exception:
        bridge_available = False
    if not bridge_available:
        raise click.UsageError(
            f"'{command_name}' requires contao-cli-bridge which is not installed on this server.\n"
            f"Install with: composer require webwerkwien/contao-cli-bridge"
        )
