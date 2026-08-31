"""Contao form generator (tl_form, tl_form_field)."""
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.utils.table_parser import parse_table


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


# --- write access (needs contao-ai-core-bundle) ---------------------------
#
# The two listings above predate this and still parse Symfony's ASCII table out
# of `doctrine:query:sql`. Everything below goes through the bundle and answers
# with JSON. Migrating the listings onto `record:list` is a separate, tracked
# change — it would alter their output shape.

import shlex  # noqa: E402

from contao_ai_cli.core.contao_ops import (  # noqa: E402
    build_set_args, run_delete, run_json_or_raw, run_update,
)


def form_read(backend: ContaoBackend, form_id: int) -> dict:
    """Read all fields of a tl_form record."""
    return run_json_or_raw(backend, f"contao:form:read {int(form_id)}")


def form_create(backend: ContaoBackend, title: str, alias: str | None = None,
                fields: dict | None = None) -> dict:
    """Create a form.

    The alias is generated from the title when omitted, then checked: Contao
    refuses a duplicate and a purely numeric one. A duplicate alias does not
    fail at request time — it routes to whichever record comes back first.

    `recipient` and `subject` become required as soon as `sendViaEmail=1` is
    set, because they live in that subpalette. A form that only stores its
    values needs neither.
    """
    cmd = f"contao:form:create --title={shlex.quote(title)} --no-interaction"
    if alias:
        cmd += f" --alias={shlex.quote(alias)}"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def form_update(backend: ContaoBackend, form_id: int, fields: dict) -> dict:
    """Update a form."""
    return run_update(backend, "contao:form:update", form_id, fields)


def form_delete(backend: ContaoBackend, form_id: int) -> dict:
    """Delete a form with every field in it.

    `tl_form.ctable` is `tl_form_field`, so the whole definition goes. A form is
    one row; a form definition is usually a dozen. One `tl_undo` entry for the
    set — restorable with `undo restore`.
    """
    return run_delete(backend, "contao:form:delete", form_id)


def form_field_types(backend: ContaoBackend) -> dict:
    """List the field types and what each one requires.

    Worth reading before creating a field: a `submit` needs `slabel`, a `select`
    needs `name` and `options`, an `explanation` needs neither. Guessing means
    provoking an error.
    """
    return run_json_or_raw(backend, "contao:form-field:types")


def form_field_read(backend: ContaoBackend, field_id: int) -> dict:
    """Read all fields of a tl_form_field record."""
    return run_json_or_raw(backend, f"contao:form-field:read {int(field_id)}")


def form_field_create(backend: ContaoBackend, pid: int, field_type: str,
                      fields: dict | None = None) -> dict:
    """Create a form field.

    New fields are appended 128 apart, the gap Contao's back end leaves so a
    later drag can land between neighbours without renumbering.

    Options take a short form, because `select`, `radio` and `checkbox` cannot
    be created without them:

        --set options="mrs=Mrs.|mr=Mr."     value and label
        --set options="red|green|blue"      label doubles as the value
    """
    cmd = (
        f"contao:form-field:create --pid={int(pid)} "
        f"--type={shlex.quote(field_type)} --no-interaction"
    )
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def form_field_update(backend: ContaoBackend, field_id: int, fields: dict) -> dict:
    """Update a form field."""
    return run_update(backend, "contao:form-field:update", field_id, fields)


def form_field_delete(backend: ContaoBackend, field_id: int) -> dict:
    """Delete a single form field.

    No cascade. The gap it leaves in the sorting sequence is harmless — Contao
    sorts by the column and does not need the numbers to be contiguous.
    """
    return run_delete(backend, "contao:form-field:delete", field_id)
