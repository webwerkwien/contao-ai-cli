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

__version__ = "0.5.2"

CORE_BUNDLE = "webwerkwien/contao-ai-core-bundle"
BACKEND_BUNDLE = "webwerkwien/contao-ai-backend-bundle"
# The /packages/<name>.json API is cached and lags visibly behind a release —
# it still reported v0.2.7 after v0.2.9 was out. /p2/ is the metadata Composer
# itself resolves against, so it is the one that answers "is an update available".
PACKAGIST_API = f"https://repo.packagist.org/p2/{CORE_BUNDLE}.json"
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


def version_tuple(version) -> tuple:
    """
    A release version as a comparable tuple of ints; () for anything else.

    Deliberately narrow: leading `v` is dropped, numeric parts are compared, and
    anything with a non-numeric segment (`dev-main`, `1.2.0-beta`) yields () so
    the caller can treat it as "do not compare". No dependency on `packaging`,
    which is not installed alongside a pipx-installed CLI.
    """
    text = str(version or "").strip().lstrip("v")
    if not text:
        return ()
    parts = text.split(".")
    if not all(p.isdigit() for p in parts):
        return ()
    return tuple(int(p) for p in parts)


def is_newer_version(latest, current) -> bool:
    """
    True only when `latest` is genuinely ahead of `current`.

    A plain `!=` reported "update available: v0.5.0" while v0.5.1 was installed —
    every unreleased working copy looked like it was behind. Anything that cannot
    be compared as a release version (dev builds, pre-releases) returns False:
    silence is better than a wrong arrow.
    """
    a, b = version_tuple(latest), version_tuple(current)
    if not a or not b:
        return False
    # Pad so 0.5 and 0.5.0 compare equal rather than by length.
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def check_cli_update() -> dict:
    """Check if a newer version of contao-ai-cli is available on GitHub."""
    try:
        req = urllib.request.Request(CLI_RELEASES_API, headers={"User-Agent": "contao-ai-cli"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        latest = data.get("tag_name", "").lstrip("v")
        return {
            "current": __version__,
            "latest": latest,
            "update_available": is_newer_version(latest, __version__),
        }
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


def get_installed_package_versions(backend, packages) -> dict:
    """
    Installed versions of several composer packages, in one SSH round-trip.

    Returns {package: version-or-None}. None means "not in installed.json",
    which is also what you get when the file cannot be read at all — the caller
    has no way to tell those apart, so treat None as "assume not installed"
    only where that is the safe reading.
    """
    packages = list(packages)
    result = {p: None for p in packages}
    for package in packages:
        # Interpolated into a PHP string literal inside a single-quoted shell
        # argument. These are module constants, not user input, but a stray
        # quote would break out of both, so refuse rather than guess.
        if "'" in package or '"' in package or "\\" in package:
            raise ValueError(f"Refusing to query a package name with quotes: {package!r}")
    wanted = ",".join(f'"{p}"' for p in packages)
    php_code = (
        f'$w=[{wanted}];'
        'if($d=json_decode(@file_get_contents("vendor/composer/installed.json"),true)){'
        'foreach($d["packages"] as $p)'
        'if(in_array($p["name"],$w,true))echo $p["name"]," ",$p["version"],"\\n";}'
    )
    try:
        out = backend.run_raw(f"{shlex.quote(backend.php_path)} -r '{php_code}'")["stdout"]
    except Exception:
        return result
    for line in out.splitlines():
        name, _, version = line.strip().partition(" ")
        if name in result and version:
            result[name] = version
    return result


def get_core_bundle_installed_version(backend) -> str | None:
    """Return the installed version of contao-ai-core-bundle on the remote server, or None."""
    return get_installed_package_versions(backend, [CORE_BUNDLE])[CORE_BUNDLE]


def get_core_bundle_latest_version() -> str | None:
    """Return the latest stable version of contao-ai-core-bundle from Packagist."""
    try:
        req = urllib.request.Request(PACKAGIST_API, headers={"User-Agent": "contao-ai-cli"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        # /p2/ returns {"packages": {"<name>": [{"version": "v0.2.9", ...}, ...]}},
        # newest first.
        releases = data["packages"][CORE_BUNDLE]
        stable = [
            r["version"] for r in releases
            if "version" in r and not r["version"].startswith("dev-") and "dev" not in r["version"]
        ]
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


def _detect_core_bundle(backend) -> bool:
    """Check if contao-ai-core-bundle commands are available on the server."""
    try:
        result = backend.run("list")
        return "contao:user:update" in result["stdout"]
    except Exception:
        return False


def parse_set_fields(fields) -> dict:
    """
    Turn repeated `--set FIELD=VALUE` into a dict.

    A malformed entry is an error rather than something to drop: silently
    ignoring `--set titel Neu` would report a successful update that changed
    nothing.
    """
    parsed = {}
    for raw in fields:
        key, sep, value = raw.partition("=")
        if not sep or not key:
            raise click.UsageError(f"--set expects FIELD=VALUE, got: {raw!r}")
        parsed[key] = value
    return parsed


def confirm_delete(what: str, assume_yes: bool = False) -> bool:
    """
    Ask before deleting, unless told not to or nobody is there to answer.

    The Contao back end asks: DefaultOperationsListener puts
    `onclick="if(!confirm(...))return false"` on the generic delete operation of
    every DCA. A prompt here is therefore consistent with Contao rather than
    stricter than it. But this CLI is driven by agents and scripts as much as by
    people, and a prompt that nothing can answer is worse than no prompt — so it
    only appears on a terminal, and --yes skips it.
    """
    if assume_yes:
        return True
    try:
        interactive = sys.stdin.isatty()
    except Exception:
        interactive = False
    if not interactive:
        return True
    return click.confirm(f"Delete {what}?", default=False)


def _require_core_bundle(ctx, command_name: str):
    """
    Raise UsageError with an install hint if the core bundle is missing.

    Named `_require_core_bundle` until v0.5.0, after the core bundle's original name
    `contao-cli-bridge`. That collided with the unrelated `bridge` command group,
    which talks to contao-ai-backend-bundle over HTTP — and the collision was read
    as evidence that editing was meant to go through the backend, which it was not.
    """
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    try:
        with open(session_path, encoding="utf-8") as f:
            cfg = json.load(f)
        # Sessions written before v0.5.0 carry the old key.
        available = cfg.get("core_bundle_available", cfg.get("bridge_available", False))
    except Exception:
        available = False
    if not available:
        raise click.UsageError(
            f"'{command_name}' requires contao-ai-core-bundle which is not installed on this server.\n"
            f"Install with: composer require webwerkwien/contao-ai-core-bundle"
        )
