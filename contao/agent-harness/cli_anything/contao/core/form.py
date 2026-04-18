"""Contao form generator (tl_form, tl_form_field)."""
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def form_list(backend: ContaoBackend) -> list:
    """List all forms from tl_form."""
    sql = (
        "SELECT id, title, alias, method, formID, recipient, subject, "
        "storeValues, targetTable, sendViaEmail "
        "FROM tl_form ORDER BY title"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def form_fields(backend: ContaoBackend, form_id: int) -> list:
    """
    List all fields of a specific form.
    form_id: ID of the tl_form record.
    """
    sql = (
        f"SELECT id, type, name, label, mandatory, invisible, rgxp, "
        f"placeholder, value, sorting "
        f"FROM tl_form_field WHERE pid = {form_id} ORDER BY sorting"
    )
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}
