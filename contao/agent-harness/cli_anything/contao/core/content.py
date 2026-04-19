"""Contao content element management (tl_content)."""
import json
import re
import shlex

from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def _parse_headline(value: str) -> str:
    """Extract plain text from Contao's serialized headline field."""
    if not value or not value.startswith("a:"):
        return value or ""
    match = re.search(r's:5:"value";s:\d+:"([^"]*)"', value)
    return match.group(1) if match else value


def content_list(backend: ContaoBackend, article_id: int = None) -> list:
    """List content elements. Optionally filter by article ID (pid)."""
    where = f"WHERE pid = {article_id}" if article_id is not None else ""
    sql = (
        f"SELECT id, pid, type, headline, invisible, ptable "
        f"FROM tl_content {where} ORDER BY pid, sorting"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    if not parsed:
        return {"raw": result["stdout"]}
    for row in parsed:
        if isinstance(row, dict) and "headline" in row:
            row["headline"] = _parse_headline(row["headline"])
    return parsed


def content_create(backend: ContaoBackend, type: str, pid: int,
                   ptable: str = "tl_article", fields: dict = None) -> dict:
    """Create a content element via contao-cli-bridge."""
    cmd = (f"contao:content:create --type={shlex.quote(type)} --pid={pid} "
           f"--ptable={shlex.quote(ptable)} --no-interaction")
    if fields:
        cmd += " " + " ".join(f"--set {shlex.quote(f'{k}={v}')}" for k, v in fields.items())
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"status": "ok", "output": result["stdout"]}
