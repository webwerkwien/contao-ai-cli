"""Contao listing module management (contao/listing-bundle).

The listing bundle has no own table. It adds a 'listing' module type to
tl_module. Each module stores which DB table and fields to list.
"""
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table


def listing_module_list(backend: ContaoBackend) -> list:
    """List all configured listing modules (tl_module WHERE type='listing')."""
    sql = (
        "SELECT id, name, list_table, list_fields, list_where "
        # 0x6c697374696e67 = ASCII "listing" — hex avoids shell quote-escaping issues
        "FROM tl_module WHERE type = 0x6c697374696e67 ORDER BY name"
    )
    return run_sql_table(backend, sql)


def listing_data(backend: ContaoBackend, module_id: int) -> list:
    """
    Fetch the actual listing data for a given listing module ID.
    Reads list_table and list_fields from the module config, then queries
    the configured table directly.
    """
    # Get module config
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
