"""Contao newsletter management (tl_newsletter, tl_newsletter_channel)."""
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table


def channel_list(backend: ContaoBackend) -> list:
    """List all newsletter channels (tl_newsletter_channel)."""
    sql = "SELECT id, title FROM tl_newsletter_channel ORDER BY title"
    return run_sql_table(backend, sql)


def newsletter_list(backend: ContaoBackend, channel_id: int = None) -> list:
    """List newsletters. Optionally filter by channel ID (pid)."""
    where = f"WHERE pid = {int(channel_id)}" if channel_id is not None else ""
    sql = (
        f"SELECT id, pid, subject, alias, sent, date "
        f"FROM tl_newsletter {where} ORDER BY date DESC"
    )
    return run_sql_table(backend, sql)


def subscriber_list(backend: ContaoBackend, channel_id: int = None) -> list:
    """List newsletter subscribers (tl_newsletter_recipients)."""
    where = f"WHERE pid = {int(channel_id)}" if channel_id is not None else ""
    sql = (
        f"SELECT id, pid, email, active "
        f"FROM tl_newsletter_recipients {where} ORDER BY email"
    )
    return run_sql_table(backend, sql)
