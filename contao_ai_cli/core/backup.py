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

# Contao's default `contao.backup.ignore_tables`: neither backed up nor restored, so after
# a restore they still hold the state that was overwritten. A site can configure others;
# these are the ones every installation has (v1.10.0, found on showcase.conpai.eu).
RESTORE_IGNORED_TABLES = ("tl_crawl_queue", "tl_log", "tl_search", "tl_search_index", "tl_search_term")


def backup_restore(backend: ContaoBackend, backup_name: str) -> dict:
    """Restore exactly this backup, or nothing (v1.7.0).

    Up to v1.6.0 the CLI restored the *newest* backup on Contao 5.7 and 6.0, whatever
    name it was given, and reported the name asked for. Contao's BackupRestoreCommand
    reads the name only in `interact()`, which Symfony skips under `--no-interaction` --
    and the CLI always passed that. 5.3 reads it in `execute()`. Found as ".sql played
    back the newest backup" on showcase.conpai.eu (2026-10-13); the mechanism came out in
    the pre-release review.

    So: no `--no-interaction` (with a name given `interact()` returns before any
    question; Symfony 6.4 and 7.x stay interactive without a terminal), the name
    checked against `contao:backup:list` first, and Contao's own answer
    (`--format=json`, the backup it restored) compared afterwards -- which also catches
    a Symfony that does switch to non-interactive on its own.
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

    cmd = (f"{shlex.quote(backend.php_path)} bin/console contao:backup:restore "
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
    # Contao's own answer says "size":0 after a restore (showcase.conpai.eu, 2026-10-14);
    # the size and date of the file come from the list read above (v1.10.0).
    entry = next((b for b in listed if isinstance(b, dict) and b.get("name") == restored), {})
    return {"status": "restored", "backup": restored,
            "size": entry.get("size"), "createdAt": entry.get("createdAt"),
            # Not in any backup on purpose (contao.backup.ignore_tables): the search index
            # still lists the pages of the overwritten state, the log keeps its entries.
            "untouched": list(RESTORE_IGNORED_TABLES),
            "output": result["stdout"]}
