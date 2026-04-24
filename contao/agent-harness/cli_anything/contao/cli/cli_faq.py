"""
faq group — Manage Contao FAQ entries (tl_faq).
"""
import click

from cli_anything.contao.core import session as session_mod, faq as faq_mod
from .helpers import _get_backend, _output, _require_bridge


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
    _require_bridge(ctx, "faq read")
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
    _require_bridge(ctx, "faq create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_create(b, question, pid, answer, parsed),
            as_json or ctx.obj.get("as_json"))
