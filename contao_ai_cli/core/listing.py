"""Contao listing module management (contao/listing-bundle).

The listing bundle has no own table. It adds a 'listing' module type to
tl_module. Each module stores which DB table and fields to list.
"""
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import record_list, run_sql_table


def listing_module_list(backend: ContaoBackend, limit=None, offset=None) -> dict:
    """List all configured listing modules (tl_module WHERE type='listing')."""
    return record_list(
        backend, "tl_module",
        fields=["id", "name", "list_table", "list_fields", "list_where"],
        filters=["type=listing"],
        order="name ASC",
        limit=limit, offset=offset,
    )


def listing_data(backend: ContaoBackend, module_id: int, cfg: dict | None = None) -> list:
    """
    Fetch the actual listing data for a given listing module ID.

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
        cfg_sql = (
            f"SELECT list_table, list_fields, list_where "
            f"FROM tl_module WHERE id = {int(module_id)}"
        )
        rows = run_sql_table(backend, cfg_sql)
        if not rows:
            return {"error": f"Module {module_id} not found or not a listing module"}
        cfg = rows[0]

    table = cfg.get("list_table", "").strip()
    fields = cfg.get("list_fields", "").strip()
    where_clause = cfg.get("list_where", "").strip()

    if not table or not fields:
        return {"error": f"Module {module_id} has no list_table or list_fields configured"}

    # Normalize quotes: replace " with ' so the outer doctrine:query:sql "..." quoting survives
    where_clause = where_clause.replace('"', "'")
    where = f"WHERE {where_clause}" if where_clause else ""
    sql = f"SELECT {fields} FROM {table} {where} ORDER BY id"
    return run_sql_table(backend, sql)
