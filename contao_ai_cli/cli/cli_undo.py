"""
undo group — Restore deleted records (tl_undo).
"""
import click

from contao_ai_cli.core import undo as undo_mod
from .helpers import _get_backend, _output, _require_core_bundle, confirm_action


@click.group()
def undo():
    """Restore deleted records (tl_undo) — the back end's "Restore" module."""
    pass


@undo.command("list")
@click.option("--limit", default=50, show_default=True, help="How many entries to list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def undo_list_cmd(ctx, limit, as_json):
    """List restorable entries, newest first."""
    _require_core_bundle(ctx, "undo list")
    b = _get_backend(ctx.obj.get("session"))
    _output(undo_mod.undo_list(b, limit), as_json or ctx.obj.get("as_json"))


@undo.command("read")
@click.argument("undo_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def undo_read_cmd(ctx, undo_id, as_json):
    """Show what an entry would put back.

    Worth doing before restoring: reports which IDs are taken again (the
    restore would fail on those) and which columns the table has lost since
    (they come back missing).
    """
    _require_core_bundle(ctx, "undo read")
    b = _get_backend(ctx.obj.get("session"))
    _output(undo_mod.undo_read(b, undo_id), as_json or ctx.obj.get("as_json"))


@undo.command("restore")
@click.argument("undo_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def undo_restore_cmd(ctx, undo_id, yes, as_json):
    """Restore the records of an entry.

    Records come back with their original IDs, which is what makes references
    from other tables valid again. If an ID is occupied, the restore is refused
    and the entry stays — run `undo read` first to see that coming.
    """
    _require_core_bundle(ctx, "undo restore")
    if not confirm_action(
        f"Restore the records of undo entry {undo_id} into their live tables?",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(undo_mod.undo_restore(b, undo_id), as_json or ctx.obj.get("as_json"))
