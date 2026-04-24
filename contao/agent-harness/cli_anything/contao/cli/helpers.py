"""
Shared helpers for the contao-ai-cli CLI modules.
"""
import json
import sys
import urllib.request
import urllib.error
import click

from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.utils.repl_skin import ReplSkin
from cli_anything.contao.core import session as session_mod

__version__ = "0.1.0"

CORE_BUNDLE = "webwerkwien/contao-ai-core-bundle"
PACKAGIST_API = f"https://packagist.org/packages/{CORE_BUNDLE}.json"
CLI_RELEASES_API = "https://api.github.com/repos/webwerkwien/contao-ai-cli/releases/latest"
CLI_INSTALL_URL = "https://github.com/webwerkwien/contao-ai-cli.git"


def check_cli_update() -> dict:
    """Check if a newer version of contao-ai-cli is available on GitHub."""
    try:
        req = urllib.request.Request(CLI_RELEASES_API, headers={"User-Agent": "contao-ai-cli"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        latest = data.get("tag_name", "").lstrip("v")
        update_available = bool(latest) and latest != __version__
        return {"current": __version__, "latest": latest, "update_available": update_available}
    except Exception:
        return {"current": __version__, "latest": None, "update_available": False}


def get_core_bundle_installed_version(backend) -> str | None:
    """Return the installed version of contao-ai-core-bundle on the remote server, or None."""
    try:
        result = backend.run_raw(
            r"php -r '$d=json_decode(file_get_contents(\"vendor/composer/installed.json\"),true);"
            r"foreach($d[\"packages\"] as $p) if($p[\"name\"]===\"webwerkwien/contao-ai-core-bundle\") echo $p[\"version\"];'"
        )
        return result["stdout"].strip() or None
    except Exception:
        return None


def get_core_bundle_latest_version() -> str | None:
    """Return the latest stable version of contao-ai-core-bundle from Packagist."""
    try:
        req = urllib.request.Request(PACKAGIST_API, headers={"User-Agent": "contao-ai-cli"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        versions = data["package"]["versions"]
        stable = [v for v in versions if not v.startswith("dev-") and "dev" not in v]
        return stable[0].lstrip("v") if stable else None
    except Exception:
        return None

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
    """Check if contao-ai-core-bundle commands are available on the server."""
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
            f"'{command_name}' requires contao-ai-core-bundle which is not installed on this server.\n"
            f"Install with: composer require webwerkwien/contao-ai-core-bundle"
        )
