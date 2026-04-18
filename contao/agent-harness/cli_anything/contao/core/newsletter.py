"""Contao newsletter management (tl_newsletter, tl_newsletter_channel)."""
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def channel_list(backend: ContaoBackend) -> list:
    """List all newsletter channels (tl_newsletter_channel)."""
    sql = "SELECT id, title FROM tl_newsletter_channel ORDER BY title"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def newsletter_list(backend: ContaoBackend, channel_id: int = None) -> list:
    """List newsletters. Optionally filter by channel ID (pid)."""
    where = f"WHERE pid = {channel_id}" if channel_id is not None else ""
    sql = (
        f"SELECT id, pid, subject, alias, sent, date "
        f"FROM tl_newsletter {where} ORDER BY date DESC"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def subscriber_list(backend: ContaoBackend, channel_id: int = None) -> list:
    """List newsletter subscribers (tl_newsletter_recipients)."""
    where = f"WHERE pid = {channel_id}" if channel_id is not None else ""
    sql = (
        f"SELECT id, pid, email, active "
        f"FROM tl_newsletter_recipients {where} ORDER BY email"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}
