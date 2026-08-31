"""
settings group — Global Contao settings (localconfig.php).
"""
import click

from contao_ai_cli.core import settings as settings_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, confirm_action, parse_set_fields,
)


@click.group()
def settings():
    """Global Contao settings (tl_settings) — stored in localconfig.php, not in a table."""
    pass


@settings.command("read")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def settings_read_cmd(ctx, as_json):
    """Read every setting, with its value and whether it is overridden.

    `value` is what Contao uses; `persisted` says whether localconfig.php sets
    it at all. A setting can read 30 and be persisted false — that is the
    default, not a decision, and it moves when the default moves.
    """
    _require_core_bundle(ctx, "settings read")
    b = _get_backend(ctx.obj.get("session"))
    _output(settings_mod.settings_read(b), as_json or ctx.obj.get("as_json"))


@settings.command("update")
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Setting to change; repeat for several")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def settings_update_cmd(ctx, fields, yes, as_json):
    """Change settings in localconfig.php.

    This is the only write in the CLI that does not end in the database — it
    rewrites a PHP file every request reads. Mandatory settings cannot be
    emptied, and one unknown key rejects the whole call without writing.
    """
    _require_core_bundle(ctx, "settings update")
    parsed = parse_set_fields(fields)
    if not confirm_action(
        "Change " + ", ".join(sorted(parsed)) + " in localconfig.php?",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(settings_mod.settings_update(b, parsed), as_json or ctx.obj.get("as_json"))
