"""Contao content element management (tl_content)."""
import re
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    record_list, run_json_or_raw, build_set_args, run_update, run_delete,
)


def _parse_headline(value: str) -> str:
    """Extract plain text from Contao's serialized headline field."""
    if not value or not value.startswith("a:"):
        return value or ""
    match = re.search(r's:5:"value";s:\d+:"([^"]*)"', value)
    return match.group(1) if match else value


def content_list(backend: ContaoBackend, article_id: int | None = None,
                 limit=None, offset=None) -> dict:
    """List content elements. Optionally filter by article ID (pid).

    headline is an inputUnit field, so it arrives serialized; it is unpacked to
    plain text here the way it always was.
    """
    result = record_list(
        backend, "tl_content",
        fields=["id", "pid", "type", "headline", "invisible", "ptable"],
        filters=[f"pid={int(article_id)}"] if article_id is not None else None,
        order="pid ASC, sorting ASC",
        limit=limit, offset=offset,
    )

    for row in (result.get("results") or []):
        if isinstance(row, dict) and "headline" in row:
            row["headline"] = _parse_headline(row["headline"])

    return result

def content_read(backend: ContaoBackend, content_id: int) -> dict:
    """Read all fields of a tl_content record (headline deserialized)."""
    return run_json_or_raw(backend, f"contao:content:read {content_id}")


def content_create(backend: ContaoBackend, type: str, pid: int,
                   ptable: str = "tl_article", fields: dict | None = None) -> dict:
    """Create a content element via contao-ai-core-bundle."""
    cmd = (f"contao:content:create --type={shlex.quote(type)} --pid={pid} "
           f"--ptable={shlex.quote(ptable)} --no-interaction")
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def content_update(backend: ContaoBackend, content_id: int, fields: dict) -> dict:
    """Update content element fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:content:update", content_id, fields)


def content_delete(backend: ContaoBackend, content_id: int) -> dict:
    """
    Delete a content element via contao-ai-core-bundle.
    Cascades to nested content elements.
    Recoverable from the back end's "Restore" module.
    """
    return run_delete(backend, "contao:content:delete", content_id)
