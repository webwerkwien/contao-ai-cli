"""Contao news management (tl_news, tl_news_archive)."""
import json
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def news_archive_list(backend: ContaoBackend) -> list:
    """List all news archives (tl_news_archive)."""
    sql = "SELECT id, title FROM tl_news_archive ORDER BY title"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def news_list(backend: ContaoBackend, archive_id: int = None) -> list:
    """List news entries. Optionally filter by archive ID (pid)."""
    where = f"WHERE pid = {archive_id}" if archive_id is not None else ""
    sql = (
        f"SELECT id, pid, headline, alias, published, date "
        f"FROM tl_news {where} ORDER BY date DESC"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def news_create(backend: ContaoBackend, headline: str, pid: int,
                date: str = None, fields: dict = None) -> dict:
    """Create a news entry via contao-cli-bridge."""
    cmd = f"contao:news:create --headline={shlex.quote(headline)} --pid={pid} --no-interaction"
    if date:
        cmd += f" --date={shlex.quote(date)}"
    if fields:
        cmd += " " + " ".join(f"--set {shlex.quote(f'{k}={v}')}" for k, v in fields.items())
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"status": "ok", "output": result["stdout"]}
