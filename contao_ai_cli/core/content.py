"""Contao content element management (tl_content)."""
import re
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    record_list, run_json_or_raw, build_set_args, run_update, run_delete,
)


def _parse_headline(value) -> str:
    """Extract plain text from Contao's headline field.

    From core-bundle v0.16.0 it arrives as {value, unit}; older servers send the
    PHP-serialized string, which is still read here.
    """
    if isinstance(value, dict):
        return str(value.get("value") or "")
    if not value or not value.startswith("a:"):
        return value or ""
    match = re.search(r's:5:"value";s:\d+:"([^"]*)"', value)
    return match.group(1) if match else value


def content_list(backend: ContaoBackend, article_id: int | None = None,
                 limit=None, offset=None) -> dict:
    """List content elements. Optionally only the direct elements of one article.

    `pid` alone is not an article: tl_content also hangs below news, events,
    other content elements (nested elements, `ptable=tl_content`) and so on,
    and their ids share one number space with articles. Until v0.28.0
    `--article 158` filtered on pid only and returned elements of content
    element 158 next to those of article 158 (second agent test).
    An empty ptable -- Contao 4's shorthand for tl_article -- does not occur
    on Contao 5 installations (counted on all three sessions: 0).

    headline is an inputUnit field, so it arrives serialized; it is unpacked to
    plain text here the way it always was.
    """
    filters = None
    if article_id is not None:
        filters = [f"pid={int(article_id)}", "ptable=tl_article"]

    result = record_list(
        backend, "tl_content",
        fields=["id", "pid", "type", "headline", "invisible", "ptable"],
        filters=filters,
        order="pid ASC, sorting ASC",
        limit=limit, offset=offset,
    )

    for row in (result.get("results") or []):
        if isinstance(row, dict) and "headline" in row:
            row["headline"] = _parse_headline(row["headline"])

    return result

def content_find(backend: ContaoBackend, text: str, limit: int | None = None,
                 root: int | None = None, offset: int | None = None) -> dict:
    """Content elements whose headline, text or HTML contains `text` (core v1.10.0).

    Each result carries the field, a plain-text snippet, the element's visibility, its
    article, page, root and the root's language. The search index is no substitute:
    it answers pages, and a page with noindex is never in it.
    """
    cmd = "contao:content:find"
    if limit is not None:
        cmd += f" --limit={int(limit)}"
    if root is not None:
        cmd += f" --root={int(root)}"
    if offset:
        cmd += f" --offset={int(offset)}"  # core v1.12.0
    # `--` ends the options: a text like "-20% Rabatt" would otherwise be read as one
    # once the remote shell has removed the quotes.
    return run_json_or_raw(backend, f"{cmd} -- {shlex.quote(text)}")


def content_read(backend: ContaoBackend, content_id: int) -> dict:
    """Read all fields of a tl_content record (headline deserialized)."""
    return run_json_or_raw(backend, f"contao:content:read {content_id}")


def content_create(backend: ContaoBackend, type: str, pid: int | None,
                   ptable: str = "tl_article", fields: dict | None = None,
                   after: int | None = None) -> dict:
    """Create a content element via contao-ai-core-bundle.

    `after` (core v1.12.0) puts it directly behind that element, below its parent and
    parent table — so neither --pid nor --ptable goes along; the core refuses them.
    """
    if after is not None:
        cmd = f"contao:content:create --type={shlex.quote(type)} --after={int(after)} --no-interaction"
    else:
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
