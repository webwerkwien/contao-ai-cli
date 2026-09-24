"""Installing and updating the contao-ai bundles on a site (moved out of the connect wizard, 2026-09-17)."""
import json
import shlex
import urllib.request

from contao_ai_cli.cli.helpers import (
    BACKEND_BUNDLE, CORE_BUNDLE, COMPOSER_TIMEOUT,
    detect_contao_manager, get_installed_package_versions,
    get_missing_allow_plugins, is_newer_version, set_allow_plugins,
)
from contao_ai_cli.utils.contao_backend import ContaoBackendError

BUNDLES = {"core": CORE_BUNDLE, "backend": BACKEND_BUNDLE}

# The constraint written into composer.json -- per bundle, the range its README recommends.
# A plain `composer require <pkg>` would write `^0.x`, and `^<latest>` (v0.21.0-v0.21.1)
# overwrote `>=0.2 <1.0` on web.werk.wien: either caps the next minor for the Contao Manager
# and `composer update` (Nr. 52, 2026-09-17).
# v1.0.0: the core bundle is 1.x, where `^1.0` reaches every minor; a site still on
# `>=0.2 <1.0` gets it on its next `bundle update core`. The backend bundle is still 0.x,
# so its range stays open across 0.x and into a later 1.x.
CONSTRAINTS = {"core": "^1.0", "backend": ">=0.1 <2.0"}
REQUIREMENTS = {name: f"{BUNDLES[name]}:{CONSTRAINTS[name]}" for name in BUNDLES}


def get_bundle_latest_version(package: str) -> str | None:
    """Latest stable version from Packagist's /p2/ metadata (the source Composer resolves against)."""
    try:
        req = urllib.request.Request(f"https://repo.packagist.org/p2/{package}.json",
                                     headers={"User-Agent": "contao-ai-cli"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        stable = [r["version"] for r in data["packages"][package]
                  if "version" in r and "dev" not in r["version"]]
        return stable[0].lstrip("v") if stable else None
    except Exception:  # noqa: BLE001
        return None


def composer_command(backend, phar_path: str | None) -> str:
    """How Composer is reached on this site: the manager's passthrough, or plain composer.

    One implementation, because `health` now reports this string for a caller to
    use by hand (issue #58) and `composer_bundle` runs it. Two copies would be a
    documented command that is not the one we execute.
    """
    if phar_path:
        return f"{shlex.quote(backend.php_path)} {shlex.quote(phar_path)} composer"
    return "composer"


def composer_bundle(backend, requirement: str, action: str, phar_path: str | None = None,
                    timeout: int = COMPOSER_TIMEOUT) -> dict:
    """composer require|update through the Contao Manager's passthrough when there is one."""
    if action not in ("require", "update"):
        raise ValueError(f"Unsupported composer action: {action!r}")
    composer = composer_command(backend, phar_path)
    target = requirement if action == "require" else requirement.split(":", 1)[0]
    return backend.run_raw(f"{composer} {action} {shlex.quote(target)} --no-interaction", timeout=timeout)


def install_bundle(backend, name: str, action: str, allow_plugins: bool = False) -> dict:
    """
    Install or update a bundle and report only what can be read back afterwards.

    Moved out of the connect wizard (2026-09-17). Writing allow-plugins into the project
    composer.json was a yes/no question there; here it is the explicit --allow-plugins,
    so an agent has to ask the user before it passes it.
    """
    package = BUNDLES[name]
    base = {"bundle": name, "package": package}

    # Probed before anything else (review 2026-09-17): every helper below this
    # catches ContaoBackendError on its own and answers "nothing found", so an
    # unreachable server used to read as "composer.json does not allow
    # <plugins>" -- a refusal about the wrong thing entirely.
    try:
        backend.run("--version")
    except ContaoBackendError as e:
        return {**base, "status": "error", "code": 1, "message": f"server not reachable: {e}"}

    before = get_installed_package_versions(backend, [package])[package]

    if action == "install" and before is not None:
        return {**base, "status": "ok", "changed": False, "installed": before,
                "message": f"{package} is already installed ({before})."}
    latest = None
    if action == "update":
        if before is None:
            return {**base, "status": "error", "code": 1,
                    "message": f"{package} is not installed. Use: bundle install {name}"}
        latest = get_bundle_latest_version(package)
        if latest is None:
            return {**base, "status": "error", "code": 1,
                    "message": "Could not reach Packagist, nothing was changed."}
        if not str(before).startswith("dev-") and not is_newer_version(latest, before):
            return {**base, "status": "ok", "changed": False, "installed": before,
                    "message": f"{package} {before} is up to date."}

    requirement = REQUIREMENTS[name]
    manager = detect_contao_manager(backend)
    written: list[str] = []
    try:
        if not manager["available"]:
            missing = get_missing_allow_plugins(backend)
            if missing and not allow_plugins:
                return {**base, "status": "error", "code": 1, "missingAllowPlugins": missing,
                        "message": "No Contao Manager found, and composer.json does not allow "
                                   f"{', '.join(missing)}. Nothing was changed. Pass --allow-plugins "
                                   "to write them into the project composer.json (ask the user first)."}
            if missing:
                set_allow_plugins(backend, missing)
                written = missing
        # Both install and update run `require` with the range -- `composer update`
        # never leaves the constraint already on disk, which is exactly the boundary
        # an update needs to cross (see CONSTRAINTS).
        composer_bundle(backend, requirement, "require",
                        manager["phar_path"] if manager["available"] else None)
        backend.run("cache:warmup --env=prod")
    except ContaoBackendError as e:
        return {**base, "status": "error", "code": 1, "allowPluginsWritten": written,
                "message": f"{action} failed: {e}"}

    after = get_installed_package_versions(backend, [package])[package]
    if after is None:
        return {**base, "status": "error", "code": 1, "allowPluginsWritten": written,
                "message": f"Composer finished, but {package} is not installed afterwards."}

    if action == "update" and str(after).lstrip("v") != str(latest).lstrip("v"):
        # Composer exits 0 with an older version when something else holds the newest back
        # (a PHP requirement, a locked dependency) -- and has rewritten composer.json and the
        # lock by then. Say so (pre-release review 2026-09-17: "nothing else was changed").
        return {**base, "status": "error", "code": 1, "allowPluginsWritten": written,
                "installed": after, "previous": before, "changed": after != before,
                "constraint": CONSTRAINTS[name],
                "message": f"Composer resolved {package} to {after}, not the newest {latest} -- another "
                           f"requirement (e.g. the PHP version or a locked dependency) holds it back. "
                           f"composer.json now requires {CONSTRAINTS[name]} and the lock file was updated."}

    result = {**base, "status": "ok", "changed": after != before, "installed": after,
              "previous": before, "via": "contao-manager" if manager["available"] else "composer",
              "constraint": CONSTRAINTS[name]}
    if written:
        result["allowPluginsWritten"] = written
    return result
