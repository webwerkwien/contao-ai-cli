"""Deleted records (tl_undo) — the back end's "Restore" module.

`version restore` has existed since the early phases and answers "this record
changed and I want it as it was". This is the other half: a record that was
*deleted*. Every delete this CLI triggers has written a `tl_undo` row since
core-bundle v0.2.8 — for a cascade, one row covering the parent and everything
under it — and until now nothing could read those rows back.

⚠️ **Records come back with their original IDs.** That is what makes the
references in other tables valid again, and it is also the one way a restore
fails: if something has taken the ID since, the insert is refused and the undo
entry is left untouched. `undo read` reports that in advance.
"""
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import run_json_or_raw

#: `data` is deliberately absent — it is a serialized blob holding every
#: restored row, and dumping it into a listing is unreadable. `undo read`
#: decodes it into a summary instead.
LIST_FIELDS = "id,pid,tstamp,fromTable,query"


def undo_list(backend: ContaoBackend, limit: int = 50) -> dict:
    """List the restorable entries, newest first."""
    return run_json_or_raw(
        backend,
        f"contao:record:list tl_undo --fields {shlex.quote(LIST_FIELDS)} "
        f"--order {shlex.quote('tstamp DESC')} --limit {int(limit)}",
    )


def undo_read(backend: ContaoBackend, undo_id: int) -> dict:
    """Show what one entry would put back.

    Decodes the payload into tables, row counts and IDs, plus the two things
    that decide whether the restore can work at all: `idsTaken` (an ID occupied
    again) and `droppedColumns` (columns the table has since lost, which Contao
    silently omits on restore).
    """
    return run_json_or_raw(backend, f"contao:undo:read {int(undo_id)}")


def undo_restore(backend: ContaoBackend, undo_id: int) -> dict:
    """Restore the records of one entry, the way the back end does.

    Follows `DC_Table::undo()`: columns the table no longer has are dropped,
    `onundo_callback` runs per row, and the undo entry is deleted **only** if
    every insert succeeded — a partial restore keeps its entry so the rest is
    not lost with it.
    """
    return run_json_or_raw(backend, f"contao:undo:restore {int(undo_id)} --no-interaction")
