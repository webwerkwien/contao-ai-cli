"""Contao content element management (tl_content)."""
import re
import shlex

from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def _parse_headline(value: str) -> str:
    """Extract plain text from Contao's serialized headline field."""
    if not value or not value.startswith("a:"):
        return value or ""
    match = re.search(r's:5:"value";s:\d+:"([^"]*)"', value)
    return match.group(1) if match else value


def content_list(backend: ContaoBackend, article_id: int = None) -> list:
    """List content elements. Optionally filter by article ID (pid)."""
    where = f"WHERE pid = {int(article_id)}" if article_id is not None else ""
    sql = (
        f"SELECT id, pid, type, headline, invisible, ptable "
        f"FROM tl_content {where} ORDER BY pid, sorting"
    )
    parsed = run_sql_table(backend, sql)
    for row in parsed:
        if isinstance(row, dict) and "headline" in row:
            row["headline"] = _parse_headline(row["headline"])
    return parsed


def content_read(backend: ContaoBackend, content_id: int) -> dict:
    """Read all fields of a tl_content record (headline deserialized)."""
    return run_json_or_raw(backend, f"contao:content:read {content_id}")


def content_create(backend: ContaoBackend, type: str, pid: int,
                   ptable: str = "tl_article", fields: dict = None) -> dict:
    """Create a content element via contao-cli-bridge."""
    cmd = (f"contao:content:create --type={shlex.quote(type)} --pid={pid} "
           f"--ptable={shlex.quote(ptable)} --no-interaction")
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)
