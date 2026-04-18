"""Contao FAQ management (tl_faq, tl_faq_category)."""
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def faq_category_list(backend: ContaoBackend) -> list:
    """List all FAQ categories (tl_faq_category)."""
    sql = "SELECT id, title FROM tl_faq_category ORDER BY id"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def faq_list(backend: ContaoBackend, category_id: int = None) -> list:
    """List FAQ entries. Optionally filter by category ID (pid)."""
    where = f"WHERE pid = {category_id}" if category_id is not None else ""
    sql = (
        f"SELECT id, pid, question, alias, published "
        f"FROM tl_faq {where} ORDER BY sorting"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}
