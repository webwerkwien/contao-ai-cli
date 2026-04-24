"""Contao news management (tl_news, tl_news_archive)."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def news_archive_list(backend: ContaoBackend) -> list:
    """List all news archives (tl_news_archive)."""
    sql = "SELECT id, title FROM tl_news_archive ORDER BY title"
    return run_sql_table(backend, sql)


def news_list(backend: ContaoBackend, archive_id: int | None = None) -> list:
    """List news entries. Optionally filter by archive ID (pid)."""
    where = f"WHERE pid = {int(archive_id)}" if archive_id is not None else ""
    sql = (
        f"SELECT id, pid, headline, alias, published, date "
        f"FROM tl_news {where} ORDER BY date DESC"
    )
    return run_sql_table(backend, sql)


def news_read(backend: ContaoBackend, news_id: int) -> dict:
    """Read all fields of a tl_news record (headline deserialized)."""
    return run_json_or_raw(backend, f"contao:news:read {news_id}")


def news_create(backend: ContaoBackend, headline: str, pid: int,
                date: str | None = None, fields: dict | None = None) -> dict:
    """Create a news entry via contao-ai-core-bundle."""
    cmd = f"contao:news:create --headline={shlex.quote(headline)} --pid={pid} --no-interaction"
    if date:
        cmd += f" --date={shlex.quote(date)}"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)
