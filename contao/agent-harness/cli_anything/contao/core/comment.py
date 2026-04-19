"""Contao comment management (tl_comments)."""
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def comment_list(backend: ContaoBackend, source: str = None, parent_id: int = None) -> list:
    """
    List comments. Optionally filter by source table and/or parent ID.
    source: e.g. 'tl_news', 'tl_page', 'tl_faq'
    parent_id: ID of the parent record (pid)
    """
    conditions = []
    if source:
        safe_source = source.replace("'", "''")
        conditions.append(f"source = '{safe_source}'")
    if parent_id is not None:
        conditions.append(f"parent = {parent_id}")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        f"SELECT id, source, parent, date, name, email, comment, published "
        f"FROM tl_comments {where} ORDER BY date DESC"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}
