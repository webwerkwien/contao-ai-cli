"""
form group — Manage Contao forms (tl_form / tl_form_field).
"""
import click

from cli_anything.contao.core import session as session_mod, form as form_mod
from .helpers import _get_backend, _output


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
