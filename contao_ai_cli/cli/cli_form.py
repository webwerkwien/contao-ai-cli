"""
form group — Manage Contao forms (tl_form / tl_form_field).
"""
import click

from contao_ai_cli.core import session as session_mod, form as form_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def form():
    """Manage Contao forms (tl_form / tl_form_field)."""
    pass


@form.command("list")
@click.pass_context
def form_list_cmd(ctx):
    """List all forms."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(form_mod.form_list(b), ctx.obj.get("as_json"))


@form.command("fields")
@click.argument("form_id", type=int)
@click.pass_context
def form_fields_cmd(ctx, form_id):
    """List all fields of a form (form_id = ID from tl_form)."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(form_mod.form_fields(b, form_id), ctx.obj.get("as_json"))


# --- the form itself ------------------------------------------------------


@form.command("read")
@click.argument("form_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_read_cmd(ctx, form_id, as_json):
    """Read all fields of a form."""
    _require_core_bundle(ctx, "form read")
    b = _get_backend(ctx.obj.get("session"))
    _output(form_mod.form_read(b, form_id), as_json or ctx.obj.get("as_json"))


@form.command("create")
@click.option("--title", required=True, help="Form title")
@click.option("--alias", default=None, help="Form alias (generated from the title if omitted)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_create_cmd(ctx, title, alias, fields, as_json):
    """Create a form.

    --set sendViaEmail=1 also requires recipient and subject: they live in that
    subpalette, so a form that only stores its values needs neither. The alias
    is generated from the title when omitted, then checked for duplicates.
    """
    _require_core_bundle(ctx, "form create")
    b = _get_backend(ctx.obj.get("session"))
    _output(form_mod.form_create(b, title, alias, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@form.command("update")
@click.argument("form_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_update_cmd(ctx, form_id, ids, ids_from_file, fields, as_json):
    """Update a form, or many at once."""
    _require_core_bundle(ctx, "form update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:form:update", form_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@form.command("delete")
@click.argument("form_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_delete_cmd(ctx, form_id, yes, as_json):
    """Delete a form with every field in it.

    A form is one row; a form definition is usually a dozen. Restorable as one
    entry with `undo restore`.
    """
    _require_core_bundle(ctx, "form delete")
    if not confirm_delete(f"form {form_id} AND every field of its definition", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(form_mod.form_delete(b, form_id), as_json or ctx.obj.get("as_json"))


# --- the fields -----------------------------------------------------------


@form.command("field-types")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_field_types_cmd(ctx, as_json):
    """List the field types and what each one requires.

    Read this before creating a field: a submit needs slabel, a select needs
    name and options, an explanation needs neither.
    """
    _require_core_bundle(ctx, "form field-types")
    b = _get_backend(ctx.obj.get("session"))
    _output(form_mod.form_field_types(b), as_json or ctx.obj.get("as_json"))


@form.command("field-read")
@click.argument("field_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_field_read_cmd(ctx, field_id, as_json):
    """Read all fields of a form field."""
    _require_core_bundle(ctx, "form field-read")
    b = _get_backend(ctx.obj.get("session"))
    _output(form_mod.form_field_read(b, field_id), as_json or ctx.obj.get("as_json"))


@form.command("field-create")
@click.option("--form", "pid", type=int, required=True, help="Form ID the field belongs to")
@click.option("--type", "field_type", required=True, help="Field type, e.g. text, select, submit")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_field_create_cmd(ctx, pid, field_type, fields, as_json):
    """Create a form field, appended to the end of the form.

    Options take a short form, because select, radio and checkbox cannot be
    created without them:

      --set options="mrs=Mrs.|mr=Mr."     value and label
      --set options="red|green|blue"      label doubles as the value
    """
    _require_core_bundle(ctx, "form field-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(form_mod.form_field_create(b, pid, field_type, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@form.command("field-update")
@click.argument("field_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_field_update_cmd(ctx, field_id, ids, ids_from_file, fields, as_json):
    """Update a form field, or many at once."""
    _require_core_bundle(ctx, "form field-update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:form-field:update", field_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@form.command("field-delete")
@click.argument("field_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def form_field_delete_cmd(ctx, field_id, yes, as_json):
    """Delete a single form field."""
    _require_core_bundle(ctx, "form field-delete")
    if not confirm_delete(f"form field {field_id}", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(form_mod.form_field_delete(b, field_id), as_json or ctx.obj.get("as_json"))
