"""
The undo and settings groups — the last two basic-configuration gaps.

Both close a hole the 2026-08-31 backend-menu survey named:

  - **undo** — `version restore` existed; its counterpart for *deleted* records
    did not. Every delete has been writing a `tl_undo` row since core-bundle
    v0.2.8, and nothing could read one back.
  - **settings** — the only back end entry with no table behind it. `tl_settings`
    is a `DC_File`; the values live in `localconfig.php`, which is why
    `record list tl_settings` answers "No readable columns".

The command strings are the contract with the bundle, so they are what is
pinned. The rules themselves — an unknown key refused, a mandatory setting not
emptied, an entry kept when a restore fails — live in the bundle and are tested
there; duplicating them here would mean two places deciding the same thing.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import settings as settings_mod
from contao_ai_cli.core import undo as undo_mod


def backend():
    b = MagicMock()
    b.run.return_value = {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""}
    b.run_json.return_value = {"status": "ok"}
    return b


def sent(b) -> str:
    if b.run_json.called:
        return b.run_json.call_args[0][0]
    return b.run.call_args[0][0]


class TestUndo:
    def test_list_goes_through_the_generic_record_command(self):
        b = backend()
        undo_mod.undo_list(b)
        assert sent(b).startswith("contao:record:list tl_undo")

    def test_the_listing_leaves_out_the_payload_blob(self):
        """`data` holds every restored row serialized. In a listing it is
        unreadable — that is what `undo read` decodes."""
        b = backend()
        undo_mod.undo_list(b)
        assert "data" not in sent(b)

    def test_the_listing_is_newest_first(self):
        """The entry you want is almost always the one just created."""
        b = backend()
        undo_mod.undo_list(b)
        assert "tstamp DESC" in sent(b)

    def test_read_and_restore_use_the_dedicated_commands(self):
        b = backend()
        undo_mod.undo_read(b, 7)
        assert sent(b) == "contao:undo:read 7"

        b = backend()
        undo_mod.undo_restore(b, 7)
        assert sent(b).startswith("contao:undo:restore 7")

    def test_the_id_is_forced_to_an_integer(self):
        b = backend()
        undo_mod.undo_restore(b, "7")
        assert "contao:undo:restore 7 " in sent(b)


class TestSettings:
    def test_read_uses_the_dedicated_command(self):
        b = backend()
        settings_mod.settings_read(b)
        assert sent(b) == "contao:settings:read"

    def test_there_is_no_record_list_fallback(self):
        """`tl_settings` has no table. Reaching for the generic reader here
        would produce "No readable columns" and look like a bug."""
        b = backend()
        settings_mod.settings_read(b)
        assert "record:list" not in sent(b)

    def test_update_passes_the_fields_through(self):
        b = backend()
        settings_mod.settings_update(b, {"adminEmail": "a@b.c", "resultsPerPage": "50"})
        cmd = sent(b)
        assert cmd.startswith("contao:settings:update")
        assert "adminEmail=a@b.c" in cmd
        assert "resultsPerPage=50" in cmd

    def test_a_value_with_spaces_survives_the_shell(self):
        """`build_set_args` quotes the whole `field=value` pair, not the value
        alone — so the date format reaches the server as one argument."""
        b = backend()
        settings_mod.settings_update(b, {"dateFormat": "d. F Y"})
        assert "'dateFormat=d. F Y'" in sent(b)


class TestRegistration:
    """A command nobody can reach is the failure this project already had once:
    `record:list` sat in the bundle for weeks with no way to call it."""

    def test_both_groups_are_reachable_from_the_top_level(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "undo" in result.output
        assert "settings" in result.output

    def test_the_undo_subcommands_are_wired(self):
        result = CliRunner().invoke(cli, ["undo", "--help"])
        assert result.exit_code == 0
        for sub in ("list", "read", "restore"):
            assert sub in result.output

    def test_the_settings_subcommands_are_wired(self):
        result = CliRunner().invoke(cli, ["settings", "--help"])
        assert result.exit_code == 0
        for sub in ("read", "update"):
            assert sub in result.output
