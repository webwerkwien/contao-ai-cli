"""Global Contao settings (tl_settings) — the back end entry with no table.

`tl_settings` is a `DC_File`, not a `DC_Table`. Its values live in
`system/config/localconfig.php` as `$GLOBALS['TL_CONFIG'][…]`, which is why
`record list tl_settings` answers "No readable columns" — correctly, since
there is no schema to read — and why this needs commands of its own.

⚠️ **This is the only write in the CLI that does not end in the database.**
Two consequences worth knowing:

  - An unknown key would be written and never read back or complained about, so
    the bundle refuses any field the DCA does not know. A typo is rejected, not
    persisted.
  - The bundle reads `localconfig.php` back after saving and reports an error if
    the key is not in it, because `Config::persist()` alone only marks the
    instance modified — the file is written on destruction.
"""
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import build_set_args, run_json_or_raw


def settings_read(backend: ContaoBackend) -> dict:
    """Read every setting the DCA defines.

    Reports `value` (what Contao uses) and `persisted` (whether
    `localconfig.php` overrides it) separately. A field can read `30` and be
    persisted `false` — nobody chose 30, it is the bundle default and moves if
    the default moves.
    """
    return run_json_or_raw(backend, "contao:settings:read")


def settings_update(backend: ContaoBackend, fields: dict) -> dict:
    """Change settings in localconfig.php.

    Mandatory settings cannot be emptied, and one unknown key rejects the whole
    call without writing anything.
    """
    cmd = "contao:settings:update --no-interaction"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)
