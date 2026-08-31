"""
The user-group and member-group groups — the permission tables.

`tl_user_group` was the largest write gap left after the theme layer: readable
through the generic `record` group since 2026-08-31, writable nowhere. It is
the record that decides what a back end editor can do, so "create a user" was
only ever half an answer.

The command strings are the contract with the bundle, so they are what is
pinned here. Two points get tests of their own because they are the ones a
caller gets wrong:

  - `options` exists because a wrong permission value does not fail. It is
    stored, grants nothing, and reports success. Guessing does not self-correct.
  - `update` replaces a permission list rather than extending it.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import member_group as member_group_mod
from contao_ai_cli.core import user_group as user_group_mod


def backend():
    b = MagicMock()
    b.run.return_value = {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""}
    b.run_json.return_value = {"status": "ok"}
    return b


def sent(b) -> str:
    """The command string, whichever helper the module reached for."""
    if b.run_json.called:
        return b.run_json.call_args[0][0]
    return b.run.call_args[0][0]


class TestUserGroupList:
    def test_it_goes_through_the_generic_record_command(self):
        b = backend()
        user_group_mod.user_group_list(b)
        assert sent(b).startswith("contao:record:list tl_user_group")

    def test_it_does_not_list_the_permission_blobs(self):
        """Seventeen columns, most of them long serialized lists. A listing
        that dumps `alexf` is unreadable — that is what `read` is for."""
        cmd = backend()
        user_group_mod.user_group_list(cmd)
        for blob in ("alexf", "cud", "filemounts", "pagemounts"):
            assert blob not in sent(cmd)


class TestUserGroupWrites:
    def test_read_uses_the_dedicated_command(self):
        b = backend()
        user_group_mod.user_group_read(b, 3)
        assert sent(b) == "contao:user-group:read 3"

    def test_create_needs_only_a_name(self):
        b = backend()
        user_group_mod.user_group_create(b, "Editors")
        cmd = sent(b)
        assert cmd.startswith("contao:user-group:create")
        assert "--name=Editors" in cmd

    def test_a_permission_list_is_passed_through_unsplit(self):
        """The bundle serializes it from the DCA; splitting here would mean two
        places deciding what a list is."""
        b = backend()
        user_group_mod.user_group_create(b, "Editors", {"modules": "page,article,files"})
        assert "modules=page,article,files" in sent(b)

    def test_a_name_with_spaces_is_quoted(self):
        b = backend()
        user_group_mod.user_group_create(b, "Senior editors")
        assert "'Senior editors'" in sent(b)

    def test_update_uses_the_dedicated_command(self):
        b = backend()
        user_group_mod.user_group_update(b, 3, {"modules": "page"})
        assert "contao:user-group:update" in sent(b)

    def test_delete_uses_the_dedicated_command(self):
        b = backend()
        user_group_mod.user_group_delete(b, 3)
        assert "contao:user-group:delete" in sent(b)


class TestUserGroupOptions:
    def test_without_a_table_it_asks_for_the_install_wide_sets(self):
        b = backend()
        user_group_mod.user_group_options(b)
        assert sent(b) == "contao:user-group:options"

    def test_a_table_is_passed_along(self):
        b = backend()
        user_group_mod.user_group_options(b, "tl_news")
        assert sent(b) == "contao:user-group:options --table=tl_news"


class TestMemberGroup:
    def test_list_goes_through_the_generic_record_command(self):
        b = backend()
        member_group_mod.member_group_list(b)
        assert sent(b).startswith("contao:record:list tl_member_group")

    def test_the_listing_shows_whether_a_redirect_is_set(self):
        """`redirect`/`jumpTo` is the one thing that distinguishes two
        otherwise identical member groups."""
        b = backend()
        member_group_mod.member_group_list(b)
        cmd = sent(b)
        assert "redirect" in cmd and "jumpTo" in cmd

    def test_create_passes_the_subpalette_fields_through(self):
        """The rule itself lives in the bundle, which reads it from the DCA.
        The CLI's job is not to duplicate it — only to carry the values."""
        b = backend()
        member_group_mod.member_group_create(b, "Members", {"redirect": "1", "jumpTo": "7"})
        cmd = sent(b)
        assert "redirect=1" in cmd
        assert "jumpTo=7" in cmd

    def test_read_update_and_delete_use_the_dedicated_commands(self):
        for call, expected in (
            (lambda b: member_group_mod.member_group_read(b, 2), "contao:member-group:read"),
            (lambda b: member_group_mod.member_group_update(b, 2, {"name": "x"}), "contao:member-group:update"),
            (lambda b: member_group_mod.member_group_delete(b, 2), "contao:member-group:delete"),
        ):
            b = backend()
            call(b)
            assert expected in sent(b)


class TestRegistration:
    """A command nobody can reach is the failure this project already had once:
    `record:list` existed in the bundle for weeks with no way to call it."""

    def test_both_groups_are_reachable_from_the_top_level(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "user-group" in result.output
        assert "member-group" in result.output

    def test_the_user_group_subcommands_are_all_wired(self):
        result = CliRunner().invoke(cli, ["user-group", "--help"])
        assert result.exit_code == 0
        for sub in ("list", "read", "create", "update", "delete", "options"):
            assert sub in result.output

    def test_the_member_group_subcommands_are_all_wired(self):
        result = CliRunner().invoke(cli, ["member-group", "--help"])
        assert result.exit_code == 0
        for sub in ("list", "read", "create", "update", "delete"):
            assert sub in result.output
