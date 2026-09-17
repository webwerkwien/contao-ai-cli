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

# Composer package argument per bundle. The backend bundle is pre-1.0 and pinned as
# the README documents it; the core bundle takes Composer's default constraint.
REQUIREMENTS = {"core": CORE_BUNDLE, "backend": f"{BACKEND_BUNDLE}:>=0.1 <1.0"}


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


def composer_bundle(backend, requirement: str, action: str, phar_path: str | None = None,
                    timeout: int = COMPOSER_TIMEOUT) -> dict:
    """composer require|update through the Contao Manager's passthrough when there is one."""
    if action not in ("require", "update"):
        raise ValueError(f"Unsupported composer action: {action!r}")
    if phar_path:
        composer = f"{shlex.quote(backend.php_path)} {shlex.quote(phar_path)} composer"
    else:
        composer = "composer"
    target = requirement if action == "require" else requirement.split(":", 1)[0]
    return backend.run_raw(f"{composer} {action} {shlex.quote(target)} --no-interaction", timeout=timeout)


def _update_requirement(name: str, package: str, latest: str) -> str:
    """
    The requirement `bundle update` passes to `composer require`.

    A plain `composer require <pkg>` with no constraint writes `^<next-minor>`
    into composer.json (README), and every later `composer update <pkg>` stays
    inside whatever constraint is already on disk -- it is the constraint, not
    the installed version, that decides how far an update can go. Pinning it to
    the version just read from Packagist is what actually crosses a 0.x minor
    (review 2026-09-17). The backend bundle keeps its own permanent range
    instead of chasing latest one release at a time.
    """
    if name == "backend":
        return REQUIREMENTS["backend"]
    return f"{package}:^{latest}"


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

    requirement = REQUIREMENTS[name] if action == "install" else _update_requirement(name, package, latest)
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
        # Both install and update run `require` with an explicit constraint --
        # `composer update` never leaves the constraint already on disk, which
        # is exactly the boundary an update needs to cross (see
        # _update_requirement).
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
        return {**base, "status": "error", "code": 1, "allowPluginsWritten": written, "installed": after,
                "message": f"Composer installed {after}, expected {latest}. Nothing else was changed."}

    result = {**base, "status": "ok", "changed": after != before, "installed": after,
              "previous": before, "via": "contao-manager" if manager["available"] else "composer"}
    if written:
        result["allowPluginsWritten"] = written
    return result
