"""
record group — table-agnostic access to any Contao table that has a DCA.

Every other read group in this CLI is tied to one entity, so a table without a
dedicated command — `tl_image_size`, `tl_theme`, `tl_module`, or anything a
third-party extension brings along — was unreachable. The core bundle has
covered that case since its early releases; this CLI just never called it.
See core/record.py for why.
"""
import click

from contao_ai_cli.core import record as record_mod
from .helpers import _get_backend, _output, _require_core_bundle


@click.group()
def record():
    """Read any Contao table that has a DCA (incl. extension tables)."""
    pass


@record.command("list")
@click.argument("table")
@click.option("--limit", type=int, default=None,
              help="Max rows. Server default 20, server maximum 100.")
@click.option("--offset", type=int, default=None, help="Skip this many rows.")
@click.option("--order", default=None,
              help='ORDER BY clause over DCA columns, e.g. "tstamp DESC". Max 3 columns.')
@click.option("--filter", "filters", multiple=True,
              help='Equality filter "field=value", repeatable. Max 10.')
@click.option("--fields", default=None,
              help="Comma-separated columns. Omitted = curated default for the table.")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def record_list_cmd(ctx, table, limit, offset, order, filters, fields, as_json):
    """List records from TABLE.

    TABLE is any table with a DCA — the server derives the allowed columns,
    filters and sort keys from it and rejects anything else, so an extension's
    own table works exactly like a core one.

    \b
    Examples:
      contao-ai-cli --session c5 record list tl_image_size
      contao-ai-cli --session c5 record list tl_page --filter published=1 --limit 50
      contao-ai-cli --session c5 record list tl_content --fields id,type,headline
    """
    _require_core_bundle(ctx, "record list")
    b = _get_backend(ctx.obj.get("session"))
    _output(
        record_mod.record_list(b, table, limit, offset, order, filters, fields),
        as_json or ctx.obj.get("as_json"),
    )


@record.command("schema")
@click.argument("table")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def record_schema_cmd(ctx, table, as_json):
    """Show the live DCA field definitions for TABLE.

    Straight JSON from the server. The `schema` group is a different thing: it
    parses `debug:dca` text output into a local cache that other commands
    validate against. This one caches nothing and answers with whatever the
    server declares right now.
    """
    _require_core_bundle(ctx, "record schema")
    b = _get_backend(ctx.obj.get("session"))
    _output(record_mod.dca_schema(b, table), as_json or ctx.obj.get("as_json"))
