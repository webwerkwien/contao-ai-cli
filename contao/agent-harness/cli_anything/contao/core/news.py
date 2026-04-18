"""Contao news management (tl_news, tl_news_archive)."""
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
