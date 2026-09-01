"""Contao page management (tl_page)."""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    record_list, run_json_or_raw, build_set_args, run_update, run_delete, run_publish,
)


def page_list(backend: ContaoBackend, pid: int | None = None,
              limit=None, offset=None) -> dict:
    """List pages. Optionally filter by parent ID."""
    return record_list(
        backend, "tl_page",
        fields=["id", "pid", "title", "alias", "type", "published", "hide"],
        filters=[f"pid={int(pid)}"] if pid is not None else None,
        order="sorting ASC",
        limit=limit, offset=offset,
    )


def page_tree(backend: ContaoBackend, root: int | None = None, depth: int | None = None) -> dict:
    """
    The page tree, built on the server.

    Used to be a SELECT over every page, nested in Python. That could not move
    to record:list — its 100-row cap is passed by any real site (wienerwandern.at
    has 283 pages).

    **The cap was never the real problem.** Paginating around it would still
    put 80 KB of JSON in front of the caller, for a question that is almost
    never "all 283 pages" but "what hangs under this node". Contao answers it
    the same way: the back end tree renders one level and keeps the expanded
    state per node, and `Database::getChildRecords()` descends level by level
    where a whole subtree is genuinely needed.

    So the depth is the control, not the row count. The default of 2 returns the
    roots and their children; `truncated` in the answer says whether pages exist
    below the cut, so a depth-limited tree cannot be mistaken for a complete one.
    """
    cmd = "contao:page:tree"
    if root is not None:
        cmd += f" --root={int(root)}"
    if depth is not None:
        cmd += f" --depth={int(depth)}"
    return run_json_or_raw(backend, cmd)


def page_read(backend: ContaoBackend, page_id: int) -> dict:
    """Read all fields of a tl_page record incl. resolved effective layout."""
    return run_json_or_raw(backend, f"contao:page:read {page_id}")


def page_create(backend: ContaoBackend, title: str, pid: int = 0,
                type: str = "regular", alias: str = "", language: str = "de",
                fields: dict | None = None) -> dict:
    """Create a page via contao-ai-core-bundle."""
    cmd = (f"contao:page:create --title={shlex.quote(title)} --pid={pid} "
           f"--type={shlex.quote(type)} --language={shlex.quote(language)} --no-interaction")
    if alias:
        cmd += f" --alias={shlex.quote(alias)}"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def page_update(backend: ContaoBackend, page_id: int, fields: dict) -> dict:
    """Update page fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:page:update", page_id, fields)


def page_delete(backend: ContaoBackend, page_id: int) -> dict:
    """
    Delete a page via contao-ai-core-bundle.
    Cascades to the subpage tree, its articles and their content elements.
    Recoverable from the back end's "Restore" module.
    """
    return run_delete(backend, "contao:page:delete", page_id)


def page_publish(backend: ContaoBackend, page_id: int, published: bool = True) -> dict:
    """Publish or unpublish a page via contao-ai-core-bundle."""
    return run_publish(backend, "contao:page:publish", page_id, published)
