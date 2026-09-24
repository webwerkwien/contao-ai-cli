"""
schema group — DCA schema sync — fetch field definitions from the live server.
"""
import os
import click

from contao_ai_cli.core import session as session_mod, dca_schema
from .helpers import _get_backend, _output


@click.group()
def schema():
    """DCA schema sync — fetch field definitions from the live server."""
    pass


@schema.command("sync")
@click.argument("table", default="")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_sync(ctx, table, as_json):
    """Sync DCA schema for TABLE (or all default tables if omitted).

    Fetches field definitions from the live server and stores them locally
    so CLI commands can validate against the project's actual DCA config.

    Default tables: tl_user, tl_page, tl_article, tl_content, tl_member
    """
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    if table:
        result = dca_schema.sync_table(b, table, session_path)
        fields = result["fields"]
        mandatory = [f for f, d in fields.items() if d.get("mandatory")]
        summary = {
            "table": table,
            "fetched": result["fetched"],
            "total_fields": len(fields),
            "mandatory_fields": mandatory,
        }
        _output(summary, as_json or ctx.obj.get("as_json"))
    else:
        results = dca_schema.sync_all(b, session_path)
        summary = {}
        for tbl, res in results.items():
            if "error" in res:
                summary[tbl] = {"status": "error", "message": res["error"]}
            else:
                mandatory = [f for f, d in res["fields"].items() if d.get("mandatory")]
                summary[tbl] = {
                    "status": "ok",
                    "total_fields": len(res["fields"]),
                    "mandatory_fields": mandatory,
                }
        _output(summary, as_json or ctx.obj.get("as_json"))


@schema.command("show")
@click.argument("table")
@click.option("--mandatory-only", is_flag=True, help="Show only mandatory fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_show(ctx, table, mandatory_only, as_json):
    """Show cached DCA schema for TABLE."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    rows = dca_schema.field_summary(table, session_path)
    if not rows:
        raise click.ClickException(
            f"No schema for '{table}'. Run: schema sync {table}"
        )
    if mandatory_only:
        rows = [r for r in rows if r["mandatory"]]
    _output(rows, as_json or ctx.obj.get("as_json"))


@schema.command("palette")
@click.argument("table")
@click.option("--set", "set_fields", multiple=True, metavar="FIELD=VALUE",
              help="The record whose palette counts, e.g. --set type=unfiltered_html")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_palette(ctx, table, set_fields, as_json):
    """Which fields a record of this kind actually has, and which are mandatory.

    The server builds Contao's own palette for the record described by --set, so
    selectors, sub-palettes and onpalette callbacks decide, exactly as in the
    back end:

        schema palette tl_content --set type=unfiltered_html
        -> fields: type, title, unfilteredHtml, customTpl, protected, ...

    Ask this before writing to a typed record for the first time. Contao has
    element types whose field is not named after them -- an `unfiltered_html`
    element stores its markup in `unfilteredHtml`, and the `html` column next to
    it belongs to the separate `html` element and stays empty. Reading that empty
    column tells you nothing; the palette does.

    Same answer as `schema mandatory --set ...`, which is where this lived until
    v1.1.0 and still works. It was not findable there (issue #56): nobody looking
    for the fields of a type searches under "mandatory".
    """
    if not set_fields:
        raise click.UsageError(
            "schema palette needs the record: --set type=... (a table has one palette per type). "
            "For every field that is mandatory somewhere in the table, use: schema mandatory " + table
        )
    ctx.invoke(schema_mandatory, table=table, set_fields=set_fields, as_json=as_json)


@schema.command("mandatory")
@click.argument("table")
@click.option("--set", "set_fields", multiple=True, metavar="FIELD=VALUE",
              help="The record whose palette counts, e.g. --set type=root --set enableCsp=1")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_mandatory(ctx, table, set_fields, as_json):
    """List mandatory fields for TABLE.

    With --set, the server builds Contao's own palette for that record and answers
    only its mandatory fields — `--set type=root` for a root page (core-bundle
    v0.16.0). Without, every field of the table that is mandatory in some palette.

    The --set form is also `schema palette`, which is the name to reach for when
    the question is "which fields does this kind of record have".
    """
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    if set_fields:
        record = {}
        for pair in set_fields:
            if "=" not in pair:
                raise click.UsageError(f"--set expects FIELD=VALUE, got {pair!r}")
            k, v = pair.split("=", 1)
            record[k.strip()] = v
        b = _get_backend(session_path)
        _output(dca_schema.palette(b, table, record), as_json or ctx.obj.get("as_json"))
        return
    fields = dca_schema.mandatory_fields(table, session_path)
    if not fields:
        schema_data = dca_schema.load_schema(table, session_path)
        if schema_data is None:
            raise click.ClickException(
                f"No schema for '{table}'. Run: schema sync {table}"
            )
    _output({"table": table, "mandatory": fields}, as_json or ctx.obj.get("as_json"))


@schema.command("resolve")
@click.argument("table", default="")
@click.argument("field", default="")
@click.option("--set", "set_fields", multiple=True, metavar="FIELD=VALUE",
              help="Record values the options depend on, e.g. --set type=text for the templates of a text element")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_resolve(ctx, table, field, set_fields, as_json):
    """Resolve __callback__ options in cached schemas.

    With TABLE: resolves all __callback__ fields in that table.
    With TABLE FIELD: resolves only that specific field.
    Without arguments: resolves all synced tables.

    Asks the installation first (core-bundle v0.16.0), so page types and templates
    a bundle adds are included; falls back to built-in lists on an older core-bundle.
    Updates the local schema cache in-place.
    """
    record = {}
    for pair in set_fields:
        if "=" not in pair:
            raise click.UsageError(f"--set expects FIELD=VALUE, got {pair!r}")
        k, v = pair.split("=", 1)
        record[k.strip()] = v
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)

    if table:
        try:
            results = dca_schema.resolve_callback_options(b, table, session_path,
                                                          field or None, record=record or None)
        except ValueError as e:
            raise click.ClickException(str(e))
        _output({table: results}, as_json or ctx.obj.get("as_json"))
    else:
        # Resolve all synced tables
        schema_dir = dca_schema._schema_dir(session_path)
        if not os.path.isdir(schema_dir):
            raise click.ClickException("No schemas synced yet. Run: schema sync")
        import glob as _glob
        tables = [
            os.path.splitext(os.path.basename(p))[0]
            for p in _glob.glob(os.path.join(schema_dir, '*.json'))
        ]
        all_results = {}
        for tbl in sorted(tables):
            try:
                res = dca_schema.resolve_callback_options(b, tbl, session_path)
                if res:
                    all_results[tbl] = res
            except Exception as e:
                all_results[tbl] = {'error': str(e)}
        _output(all_results, as_json or ctx.obj.get("as_json"))
