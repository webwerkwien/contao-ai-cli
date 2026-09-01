"""Contao article management (tl_article)."""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    record_list, run_json_or_raw, build_set_args, run_update, run_delete,
)


def article_list(backend: ContaoBackend, page_id: int | None = None,
                 limit=None, offset=None) -> dict:
    """List articles. Optionally filter by page ID (pid)."""
    return record_list(
        backend, "tl_article",
        fields=["id", "pid", "title", "alias", "published", "inColumn"],
        filters=[f"pid={int(page_id)}"] if page_id is not None else None,
        order="pid ASC, sorting ASC",
        limit=limit, offset=offset,
    )


def article_read(backend: ContaoBackend, article_id: int) -> dict:
    """Read all fields of a tl_article record."""
    return run_json_or_raw(backend, f"contao:article:read {article_id}")


def article_create(backend: ContaoBackend, title: str, pid: int,
                   in_column: str = "main", fields: dict | None = None) -> dict:
    """Create an article via contao-ai-core-bundle."""
    cmd = (f"contao:article:create --title={shlex.quote(title)} --pid={pid} "
           f"--inColumn={shlex.quote(in_column)} --no-interaction")
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def article_update(backend: ContaoBackend, article_id: int, fields: dict) -> dict:
    """Update article fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:article:update", article_id, fields)


def article_delete(backend: ContaoBackend, article_id: int) -> dict:
    """
    Delete an article via contao-ai-core-bundle.
    Cascades to the article's content elements.
    Recoverable from the back end's "Restore" module.
    """
    return run_delete(backend, "contao:article:delete", article_id)
