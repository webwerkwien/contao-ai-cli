"""Contao article management (tl_article)."""
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def article_list(backend: ContaoBackend, page_id: int = None) -> list:
    """List articles. Optionally filter by page ID (pid)."""
    where = f"WHERE pid = {page_id}" if page_id is not None else ""
    sql = f"SELECT id, pid, title, alias, published, inColumn FROM tl_article {where} ORDER BY pid, sorting"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}
