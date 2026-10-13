"""Contao database backup management."""
import json
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend


def backup_create(backend: ContaoBackend, name: str = "") -> dict:
    cmd = "contao:backup:create"
    if name:
        cmd += f" {shlex.quote(name)}"
    result = backend.run(cmd)
    return {"status": "created", "output": result["stdout"]}


def backup_list(backend: ContaoBackend) -> dict:
    result = backend.run("contao:backup:list")
    return {"output": result["stdout"]}


# A restore reads the whole dump back; 60 s is too short for a large site.
RESTORE_TIMEOUT = 600


def backup_restore(backend: ContaoBackend, backup_name: str) -> dict:
    """Restore exactly this backup, or nothing (v1.7.0).

    Up to v1.6.0 the CLI restored the *newest* backup on Contao 5.7 and 6.0, whatever
    name it was given, and reported the name asked for. Contao's BackupRestoreCommand
    reads the name only in `interact()`, which Symfony skips under `--no-interaction` --
    and the CLI always passed that. 5.3 reads it in `execute()`. Found as ".sql played
    back the newest backup" on showcase.conpai.eu (2026-10-13); the mechanism came out in
    the pre-release review.

    So: no `--no-interaction` (with a name given `interact()` returns before any
    question; SHELL_INTERACTIVE keeps an older Symfony from switching to non-interactive
    without a terminal), the name checked against `contao:backup:list` first, and
    Contao's own answer (`--format=json`, the backup it restored) compared afterwards.
    """
    try:
        listed = json.loads(backend.run("contao:backup:list --format=json")["stdout"] or "[]")
    except ValueError as e:
        return {"status": "error", "code": 1, "backup": backup_name,
                "message": f"The backup list could not be read ({e}); nothing was restored."}
    names = [b.get("name") for b in listed if isinstance(b, dict) and b.get("name")] if isinstance(listed, list) else []
    if backup_name not in names:
        return {"status": "error", "code": 1, "backup": backup_name, "available": names[:10],
                "message": f"No backup named {backup_name!r}; nothing was restored. Use a name from "
                           f"`backup list`, exactly"
                           + (f", e.g. {names[0]} (newest)." if names else " -- there are none.")}

    cmd = (f"SHELL_INTERACTIVE=1 {shlex.quote(backend.php_path)} bin/console contao:backup:restore "
           f"{shlex.quote(backup_name)} --format=json")
    result = backend.run_raw(cmd, timeout=RESTORE_TIMEOUT, check=False)
    answer = None
    for line in reversed(result["stdout"].splitlines()):
        try:
            answer = json.loads(line)
            break
        except ValueError:
            continue

    if not isinstance(answer, dict) or result["returncode"] != 0 or "error" in answer:
        reason = answer.get("error") if isinstance(answer, dict) and answer.get("error") else (
            result["stderr"] or result["stdout"] or f"exit {result['returncode']}")
        return {"status": "error", "code": 1, "backup": backup_name,
                "message": f"Restoring {backup_name} failed: {reason}"}

    restored = answer.get("name")
    if restored != backup_name:
        # Too late to prevent, so it is said as loudly as the refusals above.
        return {"status": "error", "code": 1, "backup": backup_name, "restored": restored,
                "message": f"Contao restored {restored!r}, not {backup_name!r}: the database now holds "
                           f"that backup. Restore {backup_name!r} again or ask the user how to proceed."}
    return {"status": "restored", "backup": restored, "output": result["stdout"]}
