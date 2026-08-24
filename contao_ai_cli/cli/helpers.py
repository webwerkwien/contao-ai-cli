"""
Shared helpers for the contao-ai-cli CLI modules.
"""
import json
import shlex
import subprocess
import sys
import urllib.request
import urllib.error
import click

from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.utils.repl_skin import ReplSkin
from contao_ai_cli.core import session as session_mod

__version__ = "0.4.3"

CORE_BUNDLE = "webwerkwien/contao-ai-core-bundle"
PACKAGIST_API = f"https://packagist.org/packages/{CORE_BUNDLE}.json"
CLI_RELEASES_API = "https://api.github.com/repos/webwerkwien/contao-ai-cli/releases/latest"
CLI_INSTALL_URL = "https://github.com/webwerkwien/contao-ai-cli.git"

# Composer plugins the Contao stack needs. On a Managed Edition these are allowed
# in the Contao Manager's own config.json; only the plain-composer fallback has to
# write them into the project composer.json.
REQUIRED_COMPOSER_PLUGINS = (
    "contao-components/installer",
    "contao/manager-plugin",
)
# Contao 5 uses public/, installations carried over from Contao 4 still use web/.
MANAGER_PHAR_CANDIDATES = (
    "public/contao-manager.phar.php",
    "web/contao-manager.phar.php",
)
COMPOSER_TIMEOUT = 300
CLI_UPDATE_TIMEOUT = 300


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


def get_pipx_installed_version() -> str | None:
    """Return the contao-ai-cli version pipx currently reports, or None."""
    try:
        result = subprocess.run(
            ["pipx", "list", "--json"], capture_output=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        data = json.loads(result.stdout)
        return data["venvs"]["contao-ai-cli"]["metadata"]["main_package"]["package_version"]
    except Exception:
        return None


def install_cli_update(latest_version: str) -> dict:
    """
    Reinstall contao-ai-cli at latest_version via pipx.

    'pipx upgrade' cannot move an installation whose spec is pinned to a tag —
    'git+…@v0.4.1' resolves to v0.4.1 forever and pipx reports "already at latest
    version". So the update is a forced reinstall at the requested tag, and the
    result is read back from pipx instead of assumed.

    Returns {"installed": <version or None>, "updated": bool}.
    """
    wanted = latest_version.lstrip("v")
    try:
        subprocess.run(
            ["pipx", "install", "--force", f"git+{CLI_INSTALL_URL}@v{wanted}"],
            check=False, encoding="utf-8", errors="replace", timeout=CLI_UPDATE_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {"installed": get_pipx_installed_version(), "updated": False}
    installed = get_pipx_installed_version()
    return {"installed": installed, "updated": installed == wanted}


def get_core_bundle_installed_version(backend) -> str | None:
    """Return the installed version of contao-ai-core-bundle on the remote server, or None."""
    try:
        php_code = (
            'if($d=json_decode(@file_get_contents("vendor/composer/installed.json"),true)){'
            'foreach($d["packages"] as $p)'
            'if($p["name"]==="webwerkwien/contao-ai-core-bundle")echo $p["version"];}'
        )
        result = backend.run_raw(f"{shlex.quote(backend.php_path)} -r '{php_code}'")
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


def detect_contao_manager(backend) -> dict:
    """
    Detect whether the target is a Managed Edition driven by the Contao Manager.

    The phar is what we actually invoke, so its presence plus the manager's own
    config directory decides. 'contao/manager-bundle' in the composer.lock is
    reported alongside as a corroborating signal but is not sufficient on its own —
    without a phar there is nothing to call.

    Returns a dict with keys: phar_path, config_dir, manager_bundle, available.
    """
    # Wrapped in a subshell so a failing 'cd <contao_root>' surfaces as an error
    # instead of probing whatever directory the SSH session happened to land in.
    probe = "( " + "; ".join(
        [f'[ -f {p} ] && echo "phar={p}"' for p in MANAGER_PHAR_CANDIDATES]
        + ['[ -d contao-manager ] && echo "config_dir=1"',
           'grep -q \'"contao/manager-bundle"\' composer.lock 2>/dev/null && echo "manager_bundle=1"',
           "true"]
    ) + " )"
    result = {"phar_path": None, "config_dir": False,
              "manager_bundle": False, "available": False}
    try:
        lines = backend.run_raw(probe)["stdout"].splitlines()
    except ContaoBackendError:
        return result
    for line in lines:
        line = line.strip()
        if line.startswith("phar=") and result["phar_path"] is None:
            result["phar_path"] = line.split("=", 1)[1]
        elif line == "config_dir=1":
            result["config_dir"] = True
        elif line == "manager_bundle=1":
            result["manager_bundle"] = True
    result["available"] = bool(result["phar_path"]) and result["config_dir"]
    return result


def get_missing_allow_plugins(backend) -> list[str]:
    """
    Return the Composer plugins that are NOT yet allowed in the project composer.json.

    An empty list means composer can run without touching the file.
    """
    php_code = (
        'if($j=json_decode(@file_get_contents("composer.json"),true)){'
        '$a=$j["config"]["allow-plugins"]??null;'
        'if($a===true)echo "*";'
        'elseif(is_array($a))foreach($a as $k=>$v){if($v)echo $k,"\\n";}}'
    )
    try:
        out = backend.run_raw(f"{shlex.quote(backend.php_path)} -r '{php_code}'")["stdout"]
    except ContaoBackendError:
        # Unreadable composer.json — assume nothing is allowed and ask.
        return list(REQUIRED_COMPOSER_PLUGINS)
    allowed = {line.strip() for line in out.splitlines() if line.strip()}
    if "*" in allowed:
        return []
    return [p for p in REQUIRED_COMPOSER_PLUGINS if p not in allowed]


def set_allow_plugins(backend, plugins) -> None:
    """Write allow-plugins entries into the project composer.json. Never call unprompted."""
    for plugin in plugins:
        backend.run_raw(f"composer config {shlex.quote('allow-plugins.' + plugin)} true")


def composer_core_bundle(backend, action: str, phar_path: str | None = None,
                         timeout: int = COMPOSER_TIMEOUT) -> dict:
    """
    Run 'composer require|update' for the core bundle on the target server.

    With phar_path set the call goes through the Contao Manager's composer
    passthrough, which uses the manager's own COMPOSER_HOME — the project
    composer.json keeps its own config. Without it, plain composer is used.
    """
    if action not in ("require", "update"):
        raise ValueError(f"Unsupported composer action: {action!r}")
    if phar_path:
        composer = f"{shlex.quote(backend.php_path)} {shlex.quote(phar_path)} composer"
    else:
        composer = "composer"
    return backend.run_raw(
        f"{composer} {action} {CORE_BUNDLE} --no-interaction", timeout=timeout
    )


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
        with open(session_path, encoding="utf-8") as f:
            cfg = json.load(f)
        bridge_available = cfg.get("bridge_available", False)
    except Exception:
        bridge_available = False
    if not bridge_available:
        raise click.UsageError(
            f"'{command_name}' requires contao-ai-core-bundle which is not installed on this server.\n"
            f"Install with: composer require webwerkwien/contao-ai-core-bundle"
        )
