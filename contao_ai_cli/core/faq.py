"""Contao FAQ management (tl_faq, tl_faq_category)."""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    run_sql_table, run_json_or_raw, build_set_args, run_update, run_delete,
)


def faq_category_list(backend: ContaoBackend) -> list:
    """List all FAQ categories (tl_faq_category)."""
    sql = "SELECT id, title FROM tl_faq_category ORDER BY id"
    return run_sql_table(backend, sql)


def faq_list(backend: ContaoBackend, category_id: int | None = None) -> list:
    """List FAQ entries. Optionally filter by category ID (pid)."""
    where = f"WHERE pid = {int(category_id)}" if category_id is not None else ""
    sql = (
        f"SELECT id, pid, question, alias, published "
        f"FROM tl_faq {where} ORDER BY sorting"
    )
    return run_sql_table(backend, sql)


def faq_read(backend: ContaoBackend, faq_id: int) -> dict:
    """Read all fields of a tl_faq record."""
    return run_json_or_raw(backend, f"contao:faq:read {faq_id}")


def faq_create(backend: ContaoBackend, question: str, pid: int,
               answer: str = "", fields: dict | None = None) -> dict:
    """Create a FAQ entry via contao-ai-core-bundle."""
    cmd = f"contao:faq:create --question={shlex.quote(question)} --pid={pid} --no-interaction"
    if answer:
        cmd += f" --answer={shlex.quote(answer)}"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def faq_update(backend: ContaoBackend, faq_id: int, fields: dict) -> dict:
    """Update FAQ entry fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:faq:update", faq_id, fields)


def faq_delete(backend: ContaoBackend, faq_id: int) -> dict:
    """
    Delete a FAQ entry via contao-ai-core-bundle.
    Cascades to the entry's content elements.
    Recoverable from the back end's "Restore" module.
    """
    return run_delete(backend, "contao:faq:delete", faq_id)
