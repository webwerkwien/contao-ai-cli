"""contao:ai:apply: page, article and content writes from one plan (core v1.13.0)."""
import json

from contao_ai_cli.utils.contao_backend import ContaoBackendError

# 60 s is what every other call gets; a plan of many steps needs more. Measured
# per step during acceptance and adjusted there.
BASE_TIMEOUT = 60
PER_STEP = 2
MAX_TIMEOUT = 600


class ApplyFailed(ContaoBackendError):
    """The server refused or rolled back the plan; `payload` says where and why."""

    def __init__(self, payload: dict, returncode: int):
        self.payload = payload
        self.returncode = returncode
        super().__init__(payload.get("message") or f"apply failed (exit {returncode})")


def timeout_for(steps: int) -> int:
    return min(BASE_TIMEOUT + PER_STEP * max(steps, 0), MAX_TIMEOUT)


def run_apply(backend, plan_text: str, dry_run: bool, steps: int) -> dict:
    """Send the plan over stdin; the server checks it and runs it all or nothing."""
    cmd = "contao:ai:apply --no-interaction" + (" --dry-run" if dry_run else "")
    timeout = timeout_for(steps)
    try:
        result = backend.run(cmd, check=False, stdin_data=plan_text, timeout=timeout)
    except ContaoBackendError as exc:
        if "timed out" in str(exc):
            # The server does not stop when our connection does: the run can still
            # commit after we gave up. Saying "failed" would invite a second run.
            raise ContaoBackendError(
                f"{exc}. The plan may still have written on the server: check the "
                "pages before running it again."
            ) from exc
        raise
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        raise ContaoBackendError(
            f"apply failed (exit {result['returncode']}): "
            f"{(result.get('stderr') or result['stdout'])[:500]}"
            f"{backend.undefined_command_hint(result['stdout'], result.get('stderr', ''))}"
        ) from None
    if not isinstance(payload, dict):
        raise ContaoBackendError(f"apply failed (exit {result['returncode']}): {result['stdout'][:500]}")
    if result["returncode"] != 0 or payload.get("status") != "ok":
        raise ApplyFailed(payload, result["returncode"])
    return payload
