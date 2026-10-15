"""Contao listing module management (contao/listing-bundle).

The listing bundle has no own table. It adds a 'listing' module type to
tl_module. Each module stores which DB table and fields to list.
"""
import json

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import record_list, run_json_or_raw, run_sql_table


def listing_module_list(backend: ContaoBackend, limit=None, offset=None) -> dict:
    """List all configured listing modules (tl_module WHERE type='listing')."""
    return record_list(
        backend, "tl_module",
        fields=["id", "name", "list_table", "list_fields", "list_where"],
        filters=["type=listing"],
        order="name ASC",
        limit=limit, offset=offset,
    )


def listing_config(backend: ContaoBackend, module_id: int) -> dict:
    """The configuration of one listing module, read through the server.

    Replaces a hand-written SELECT over tl_module. The server command existed
    all along and had no caller in this CLI until `ext list` pointed at it.
    """
    return run_json_or_raw(backend, f"contao:listing:config {int(module_id)}")


class ListingError(Exception):
    """A listing module that cannot be read: missing, or without table/fields."""


def listing_data(backend: ContaoBackend, module_id: int, cfg: dict | None = None,
                 limit: int | None = None, offset: int | None = None) -> dict:
    """
    The rows a listing module shows (v1.10.0: through the server).

    contao:listing:data (core-bundle v1.9.0) runs the module's own query server-side and
    answers JSON — the caller passes nothing but the id, so the free `list_where` stays
    the site's, and the ASCII table below is not parsed. Against an older core-bundle the
    command does not exist; then the SQL path below runs as before.
    """
    cmd = f"contao:listing:data {int(module_id)}"
    if limit is not None:
        cmd += f" --limit={int(limit)}"
    if offset is not None:
        cmd += f" --offset={int(offset)}"
    result = backend.run(cmd, check=False)
    # The last line that is JSON: PHP start-up warnings can share stdout (as in backup.py).
    answer = None
    for line in reversed((result.get("stdout") or "").splitlines()):
        try:
            answer = json.loads(line)
            break
        except ValueError:
            continue
    if isinstance(answer, dict) and answer.get("status") == "ok":
        return answer
    if isinstance(answer, dict) and answer.get("status") == "error":
        raise ListingError(str(answer.get("message") or f"Module {module_id} could not be read"))
    # Only a missing command falls back. Anything else — a crash of the command — is an
    # error: the SQL path would answer unmasked values the caller did not ask for (review).
    text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
    if 'Command "contao:listing:data" is not defined' not in text and "There are no commands defined" not in text:
        raise ListingError(f"contao:listing:data {module_id} failed: {text.strip()[:300]}")
    data = _listing_data_sql(backend, module_id, cfg)
    if limit is not None or offset is not None:
        data["paging"] = "ignored: core-bundle before v1.9.0 has no contao:listing:data"
    return data


def _listing_data_sql(backend: ContaoBackend, module_id: int, cfg: dict | None = None) -> dict:
    """
    Fetch the actual listing data for a given listing module ID — the fallback for a
    core-bundle before v1.9.0.

    The one read path in this CLI that still writes its own SQL, and
    deliberately so (decision 2026-09-01). Everything else moved to
    contao:record:list, which validates table, columns, filters and order
    against the DCA — and that validation is exactly what cannot be applied
    here: `list_where` is a free SQL fragment stored in the module itself, so
    the query is configured in the site, not by the caller.

    Passing it through record:list would mean handing the server arbitrary
    WHERE clauses, which removes the point of going through record:list at all.
    Ignoring it would be worse: the command would then answer with different
    rows than the module shows in the front end.


    Pass cfg (a row from listing_module_list) to skip the first SSH roundtrip.
    Otherwise the module config is fetched from tl_module first.
    """
    if cfg is None:
        # The config half moved to contao:listing:config (2026-09-01). Only the
        # data half below still writes its own SQL, and only because list_where
        # is a free fragment configured in the site. Reading the module's own
        # settings is an ordinary lookup and had no business being raw SQL.
        answer = listing_config(backend, module_id)
        if not isinstance(answer, dict) or answer.get("status") != "ok":
            raise ListingError(f"Module {module_id} not found or not a listing module")
        cfg = answer

    table = cfg.get("list_table", "").strip()
    fields = cfg.get("list_fields", "").strip()
    where_clause = cfg.get("list_where", "").strip()

    if not table or not fields:
        raise ListingError(f"Module {module_id} has no list_table or list_fields configured")

    # Normalize quotes: replace " with ' so the outer doctrine:query:sql "..." quoting survives
    where_clause = where_clause.replace('"', "'")
    where = f"WHERE {where_clause}" if where_clause else ""
    sql = f"SELECT {fields} FROM {table} {where} ORDER BY id"
    rows = run_sql_table(backend, sql)
    # The answer every other listing gives (v0.30.0). Until then a bare list
    # here, and an error was a dict with exit code 0 (practical test 2026-09-19).
    # Values stay strings: this is a SQL table read, not record:list.
    return {"status": "ok", "module": int(module_id), "table": table,
            "count": len(rows), "results": rows}
