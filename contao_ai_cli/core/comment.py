"""Contao comment management (tl_comments)."""
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import record_list, run_delete, run_publish


def comment_list(backend: ContaoBackend, source: str | None = None,
                 parent_id: int | None = None, limit=None, offset=None) -> dict:
    """
    List comments. Optionally filter by source table and/or parent ID.
    source: e.g. 'tl_news', 'tl_page', 'tl_faq'
    parent_id: ID of the parent record (pid)

    The source used to be interpolated into the SQL with hand-rolled quote
    doubling. It is a bound parameter now, and the column name is checked
    against the DCA before the query is built.
    """
    filters = []
    if source:
        filters.append(f"source={source}")
    if parent_id is not None:
        filters.append(f"parent={int(parent_id)}")

    return record_list(
        backend, "tl_comments",
        fields=["id", "source", "parent", "date", "name", "email", "comment", "published"],
        filters=filters or None,
        order="date DESC",
        limit=limit, offset=offset,
    )


def comment_delete(backend: ContaoBackend, comment_id: int) -> dict:
    """Delete a comment via contao-ai-core-bundle."""
    return run_delete(backend, "contao:comment:delete", comment_id)


def comment_publish(backend: ContaoBackend, comment_id: int, published: bool = True) -> dict:
    """Publish or unpublish a comment — the moderation path for visitor-authored text."""
    return run_publish(backend, "contao:comment:publish", comment_id, published)
