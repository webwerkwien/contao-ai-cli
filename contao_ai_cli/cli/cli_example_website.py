"""
example-website group — Contao's example websites (core-bundle v1.9.0).
"""
import click

from contao_ai_cli.core import theme_archive as archive_mod
from contao_ai_cli.core.status import cli_prefix
from .cli_health import _session_name
from .helpers import _get_backend, _output, _require_core_bundle, confirm_escalation


@click.group("example-website")
def example_website():
    """Contao's example websites — an .sql that can replace the whole site."""


@example_website.command("import")
@click.argument("local_file", type=click.Path(dir_okay=False))
@click.option("--mode", required=True, type=click.Choice(["full", "data", "data_no_truncate"]),
              help="full: every statement, DROP and CREATE included; data: empty every tl_ table, "
                   "then the INSERTs; data_no_truncate: only the INSERTs, existing data stays")
@click.option("--admins", type=click.Choice(["both", "existing"]), default=None,
              help="When administrators exist and the file brings users: both (keep them next to the "
                   "imported ones) or existing (keep only them). Ask the operator.")
@click.option("--entry", default=None, help="Which .sql inside a .cto holding several")
@click.option("--yes", "-y", "assume_yes", is_flag=True,
              help="Import after the preview without asking; an agent passes it only after asking the operator")
@click.option("--operator", default="", help="Acting user identifier for the audit log")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def example_import_cmd(ctx, local_file, mode, admins, entry, assume_yes, operator, as_json):
    """Import an example website (.sql, or the one inside a .cto) as Contao does.

    First a preview: statements, tables, how many tables `data` empties, the existing
    administrators and whether the file brings users. Then — at a terminal after a
    question, without one only with --yes — a database backup, always, and the import.
    The answer names the backup: `backup restore <name>` is the way back, until the next
    backup made today (Contao keeps one per day).
    """
    _require_core_bundle(ctx, "example-website import")
    as_json = as_json or ctx.obj.get("as_json")
    b = _get_backend(ctx.obj.get("session"))
    try:
        with archive_mod.Upload(b, local_file, archive_mod.EXAMPLE_EXTENSIONS) as remote:
            preview = archive_mod.example_import(b, remote, mode, admins, entry, confirm=False)
            if preview.get("status") != "preview":
                _output(preview, as_json)
                ctx.exit(1)
            if preview.get("needs_admin_decision") and not admins:
                _output({**preview, "imported": False,
                         "next": "There are administrators already ({}) and the file brings users. Ask the operator: "
                                 "--admins both keeps them next to the imported ones, --admins existing keeps only them."
                                 .format(", ".join(preview.get("existing_admins") or []))}, as_json)
                ctx.exit(1)
            warnings = " ".join(preview.get("warnings") or [])
            if not assume_yes and not confirm_escalation(
                    f"Import {preview.get('file')} in mode {mode}? "
                    f"{preview.get('truncates', 0)} table(s) would be emptied; a backup is made first."
                    + (f" Warning: {warnings}" if warnings else "")):
                _output({**preview, "imported": False,
                         "next": "Nothing was imported. Show the preview to the operator; with their yes, repeat with --yes."},
                        as_json)
                return
            result = archive_mod.example_import(b, remote, mode, admins, entry, confirm=True, operator=operator)
    except archive_mod.ArchiveError as e:
        raise click.ClickException(str(e))

    if result.get("status") == "ok":
        prefix = cli_prefix(_session_name(ctx.obj.get("session")))
        steps = []
        if mode == "full":
            steps.append({"command": f"{prefix} contao migrate", "optional": False,
                          "reason": "A full import recreates tables from the file; migrations bring them to this Contao."})
        if mode in ("full", "data"):
            steps.append({"command": f"{prefix} contao filesync", "optional": False,
                          "reason": "tl_files was emptied or replaced; the file sync rebuilds it from files/."})
        steps.append({"command": f"{prefix} cache clear", "optional": False,
                      "reason": "The site changed under every page cache."})
        result["nextSteps"] = steps
    _output(result, as_json)
    if result.get("status") != "ok":
        ctx.exit(1)
