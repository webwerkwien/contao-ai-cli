"""
The state of a session: CLI, Contao, both bundles, bridge.

Built once and shared: `health` prints it, `connect` answers with it and derives
`next_steps` from it, and the update notice compares it (2026-09-17, agent-driven
onboarding). Before, the wizard in `connect` asked its own questions and `health`
collected its own state, and the two could not agree on what "update available"
meant.
"""
from contao_ai_cli.cli.helpers import (
    BACKEND_BUNDLE, CONTAO_CORE_BUNDLE, CORE_BUNDLE, check_cli_update,
    detect_contao_manager, get_installed_package_versions, is_newer_version,
)
from contao_ai_cli.core import backend_bridge as bridge_mod, session as session_mod
from contao_ai_cli.core.bundles import composer_command, get_bundle_latest_version
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError

WARNING = (
    "contao-ai-cli can change or delete data on this site irreversibly. "
    "Make sure a current backup exists before anything is written."
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


def collect_status(session_path: str) -> dict:
    """
    Gather the full picture for one session in a single call.

    Moved here unchanged in behaviour from `cli_health.py` (2026-09-17): `health`,
    `connect` and the update notice all need exactly this, and a second copy is
    how "update available" used to mean two different things in two places.
    """
    cli_update = check_cli_update()
    cli_status = {
        "installed": cli_update["current"],
        "latest": cli_update["latest"],
        "up_to_date": not cli_update["update_available"],
    }
    # Always present, never omitted: a missing key would read as "no Contao
    # here", which is never the case - only "could not look".
    core_status: dict = {"reachable": False}
    contao_status: dict = {"installed": None}
    backend_status: dict = {"installed": None, "latest": None, "update_available": False}
    # How Composer is reached on this site. Reported because nothing else we ship
    # tells a caller how to install an extension this CLI does not manage, and
    # guessing it wrong on a Managed Edition means going behind the manager's back
    # (issue #58). `via` is None only when we could not look.
    composer_status: dict = {"via": None, "command": None}
    # None = could not look, which is not the same as "not installed".
    backend_installed: bool | None = None

    # Use ContaoBackend.from_session directly instead of _get_backend so a
    # missing/incomplete session doesn't sys.exit() - status must be reportable
    # even without an active SSH session.
    try:
        backend = ContaoBackend.from_session(session_path)
        # All three in one round-trip; they live in the same installed.json.
        versions = get_installed_package_versions(backend, [CORE_BUNDLE, BACKEND_BUNDLE, CONTAO_CORE_BUNDLE])
        installed = versions[CORE_BUNDLE]
        # Read before contao_status: a test double that hands back an
        # incomplete dict (missing CONTAO_CORE_BUNDLE) must not erase a
        # backend-bundle reading that was already made.
        backend_installed = versions[BACKEND_BUNDLE] is not None
        contao_status = {"installed": versions[CONTAO_CORE_BUNDLE]}
        latest = get_bundle_latest_version(CORE_BUNDLE)
        core_status = {
            "reachable": True,
            "installed": installed,
            "latest": latest,
            "update_available": is_newer_version(latest, installed),
            "up_to_date": installed is not None and latest is not None
                          and not is_newer_version(latest, installed),
        }
        backend_latest = get_bundle_latest_version(BACKEND_BUNDLE)
        backend_status = {
            "installed": versions[BACKEND_BUNDLE],
            "latest": backend_latest,
            "update_available": is_newer_version(backend_latest, versions[BACKEND_BUNDLE]),
        }
        manager = detect_contao_manager(backend)
        phar = manager["phar_path"] if manager["available"] else None
        composer_status = {
            "via": "contao-manager" if phar else "composer",
            "command": composer_command(backend, phar),
        }
    except ContaoBackendError as e:
        core_status = {"reachable": False, "reason": f"no active session ({e})"}
    except Exception as e:  # noqa: BLE001 - a status must never kill the command that asks
        core_status = {"reachable": False, "reason": str(e)}

    cfg = session_mod.load_session(session_path)
    configured = bool(cfg.get("bridge_url") and cfg.get("bridge_token"))
    bridge_status = {
        "state": _bridge_state(backend_installed, configured),
        "installed": backend_installed,
        "configured": configured,
    }
    if configured:
        bridge_status["url"] = cfg["bridge_url"]
        bridge_status["token"] = bridge_mod.mask_token(cfg["bridge_token"])

    return {"cli": cli_status, "contao": contao_status, "core": core_status,
            "backend": backend_status, "bridge": bridge_status,
            "composer": composer_status}


def next_steps(state: dict, session_name: str | None) -> list[dict]:
    """What to do after `connect`, in order. The agent confirms each one in chat."""
    prefix = f"contao-ai-cli --session {session_name}" if session_name else "contao-ai-cli"
    steps = [{"command": f"{prefix} backup create", "optional": False,
              "reason": "A database backup before anything is written."}]

    core = state.get("core", {})
    if core.get("reachable"):
        installed = core.get("installed")
        if installed is None:
            steps.append({"command": f"{prefix} bundle install core", "optional": False,
                          "reason": "contao-ai-core-bundle is missing; without it only Contao's own console commands work."})
        elif core.get("update_available") and not str(installed).startswith("dev-"):
            steps.append({"command": f"{prefix} bundle update core", "optional": False,
                          "reason": f"contao-ai-core-bundle {installed} -> {core.get('latest')}."})

    cli = state.get("cli", {})
    if not cli.get("up_to_date", True):
        steps.append({"command": "contao-ai-cli self-update", "optional": False,
                      "reason": f"contao-ai-cli {cli.get('installed')} -> {cli.get('latest')}."})

    bridge = state.get("bridge", {})
    if core.get("reachable") and state.get("backend", {}).get("installed") is None:
        steps.append({"command": f"{prefix} bundle install backend", "optional": True,
                      "reason": "Only for bulk jobs: clone page trees, rewrite or translate whole archives in one call. Ask the user."})
    elif bridge.get("state") == "not_configured":
        steps.append({"command": f"{prefix} bridge configure --url https://<site>", "optional": True,
                      "reason": "The backend bundle is installed but has no token. The user generates it in the back end (User profile -> AI agent -> CLI bridge token)."})

    return steps
