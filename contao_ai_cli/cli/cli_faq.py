"""
faq group — Manage Contao FAQ entries (tl_faq).
"""
import click

from contao_ai_cli.core import session as session_mod, faq as faq_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    dispatch_update, parse_set_fields,
)


@click.group()
def faq():
    """Manage Contao FAQ entries (tl_faq)."""
    pass


@faq.command("categories")
@click.pass_context
def faq_categories(ctx):
    """List all FAQ categories."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(faq_mod.faq_category_list(b), ctx.obj.get("as_json"))


@faq.command("list")
@click.option("--category", "category_id", type=int, default=None,
              help="Filter by category ID")
@click.pass_context
def faq_list_cmd(ctx, category_id):
    """List FAQ entries, optionally filtered by category ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(faq_mod.faq_list(b, category_id), ctx.obj.get("as_json"))


@faq.command("read")
@click.argument("faq_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_read_cmd(ctx, faq_id, as_json):
    """Read all fields of a FAQ entry record."""
    _require_core_bundle(ctx, "faq read")
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_read(b, faq_id), as_json or ctx.obj.get("as_json"))


@faq.command("create")
@click.option("--question", required=True, help="FAQ question")
@click.option("--pid", type=int, required=True, help="FAQ category ID")
@click.option("--answer", default="", help="FAQ answer (HTML)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_create_cmd(ctx, question, pid, answer, fields, as_json):
    """Create a FAQ entry via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "faq create")
    parsed = parse_set_fields(fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_create(b, question, pid, answer, parsed),
            as_json or ctx.obj.get("as_json"))


@faq.command("update")
@click.argument("faq_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_update_cmd(ctx, faq_id, ids, ids_from_file, fields, as_json):
    """Update fields of a FAQ entry, or of many at once.

    Give one ID, or --ids=39,40,41 / --ids-from-file ids.txt to change several
    in a single connection. Every record is versioned individually either way.
    """
    _require_core_bundle(ctx, "faq update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:faq:update", faq_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@faq.command("delete")
@click.argument("faq_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_delete_cmd(ctx, faq_id, yes, as_json):
    """Delete a FAQ entry and its content elements."""
    _require_core_bundle(ctx, "faq delete")
    if not confirm_delete(f"FAQ entry {faq_id} and its content elements", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_delete(b, faq_id), as_json or ctx.obj.get("as_json"))


# --- the parent record ----------------------------------------------------


@faq.command("category-read")
@click.argument("category_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_category_read_cmd(ctx, category_id, as_json):
    """Read all fields of a FAQ category."""
    _require_core_bundle(ctx, "faq category-read")
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_category_read(b, category_id), as_json or ctx.obj.get("as_json"))


@faq.command("category-create")
@click.option("--title", required=True, help="FAQ category title")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_category_create_cmd(ctx, title, fields, as_json):
    """Create a FAQ category.

    Only --title is an option here; what else is required comes from the DCA,
    so the command reports it rather than this help text going stale.
    (headline is the heading shown on the page, as opposed to the back end label in --title.)
    """
    _require_core_bundle(ctx, "faq category-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_category_create(b, title, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@faq.command("category-update")
@click.argument("category_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_category_update_cmd(ctx, category_id, ids, ids_from_file, fields, as_json):
    """Update a FAQ category, or many at once."""
    _require_core_bundle(ctx, "faq category-update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:faq-category:update", category_id, ids, ids_from_file,
                            parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@faq.command("category-delete")
@click.argument("category_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_category_delete_cmd(ctx, category_id, yes, as_json):
    """Delete a FAQ category with everything in it.

    Restorable as one entry with `undo restore`, but the cascade is named in
    the prompt because it is not visible from the command name.
    """
    _require_core_bundle(ctx, "faq category-delete")
    if not confirm_delete(
        f"FAQ category {category_id} AND every question in it",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_category_delete(b, category_id), as_json or ctx.obj.get("as_json"))
