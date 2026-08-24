"""Contao comment management (tl_comments)."""
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import run_sql_table, run_delete, run_publish


def comment_list(backend: ContaoBackend, source: str | None = None, parent_id: int | None = None) -> list:
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
        conditions.append(f"parent = {int(parent_id)}")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        f"SELECT id, source, parent, date, name, email, comment, published "
        f"FROM tl_comments {where} ORDER BY date DESC"
    )
    return run_sql_table(backend, sql)


def comment_delete(backend: ContaoBackend, comment_id: int) -> dict:
    """Delete a comment via contao-ai-core-bundle."""
    return run_delete(backend, "contao:comment:delete", comment_id)


def comment_publish(backend: ContaoBackend, comment_id: int, published: bool = True) -> dict:
    """Publish or unpublish a comment — the moderation path for visitor-authored text."""
    return run_publish(backend, "contao:comment:publish", comment_id, published)
