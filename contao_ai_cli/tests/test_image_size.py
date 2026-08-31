"""
The image-size group.

Reading arrived on 2026-08-31 through the generic `record` group; this is the
write half. The command strings are the contract, so they are what is pinned.

One design point worth a test of its own: `image-size list` is a *preset* over
`contao:record:list`, not a command of its own on the server. The generic
command already reads any table correctly — what it cannot know is which six of
the seventeen columns someone looking at an image size wants. That is entity
knowledge, and it is the only thing the wrapper adds.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import image_size as size_mod


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


class TestList:
    def test_it_goes_through_the_generic_record_command(self):
        b = backend()
        size_mod.image_size_list(b)
        assert sent(b).startswith("contao:record:list tl_image_size")

    def test_the_listed_fields_include_what_decides_the_variant(self):
        """`width` alone invites picking a size by its number and being served
        another — `sizes` and `densities` are what the browser evaluates."""
        b = backend()
        size_mod.image_size_list(b)
        cmd = sent(b)
        for field in ("name", "width", "sizes", "densities"):
            assert field in cmd

    def test_a_theme_filter_is_passed_as_a_pid_filter(self):
        b = backend()
        size_mod.image_size_list(b, theme_id=1)
        assert "--filter pid=1" in sent(b)

    def test_without_a_theme_nothing_is_filtered(self):
        b = backend()
        size_mod.image_size_list(b)
        assert "--filter" not in sent(b)


class TestWriteCommands:
    def test_read_calls_the_dedicated_command(self):
        b = backend()
        size_mod.image_size_read(b, 5)
        assert sent(b) == "contao:image-size:read 5"

    def test_create_requires_and_passes_a_theme(self):
        b = backend()
        size_mod.image_size_create(b, "Tourenbild", 1)
        cmd = sent(b)
        assert "contao:image-size:create" in cmd
        assert "--pid=1" in cmd
        assert "Tourenbild" in cmd

    def test_create_passes_further_columns_through_set(self):
        b = backend()
        size_mod.image_size_create(b, "Tourenbild", 1, {
            "width": "1600",
            "sizes": "(max-width: 1100px) 100vw, 1000px",
        })
        cmd = sent(b)
        assert "width=1600" in cmd
        assert "1100px" in cmd

    def test_a_name_with_shell_characters_is_quoted(self):
        b = backend()
        size_mod.image_size_create(b, "gallery image | 3 / 12", 1)
        cmd = sent(b)
        # The pipe must not reach the shell as a pipe.
        assert "'gallery image | 3 / 12'" in cmd or '"gallery image | 3 / 12"' in cmd

    def test_update_goes_through_the_shared_update_helper(self):
        b = backend()
        size_mod.image_size_update(b, 5, {"width": "1600"})
        assert "contao:image-size:update" in sent(b)

    def test_delete_goes_through_the_shared_delete_helper(self):
        b = backend()
        size_mod.image_size_delete(b, 5)
        assert "contao:image-size:delete" in sent(b)


class TestMediaQueryVariants:
    """The variants are the point of an image size — the parent is the fallback."""

    def test_items_are_listed_in_sort_order(self):
        b = backend()
        size_mod.image_size_items(b, 6)
        cmd = sent(b)
        assert "tl_image_size_item" in cmd
        assert "--filter pid=6" in cmd
        assert "sorting ASC" in cmd

    def test_the_listed_variant_fields_lead_with_the_media_condition(self):
        assert size_mod.ITEM_LIST_FIELDS.split(",")[3] == "media"

    def test_item_create_requires_a_parent_and_a_media_condition(self):
        b = backend()
        size_mod.image_size_item_create(b, 6, "(max-width: 767px)")
        cmd = sent(b)
        assert "contao:image-size-item:create" in cmd
        assert "--pid=6" in cmd
        assert "max-width: 767px" in cmd

    def test_a_media_condition_with_parentheses_is_quoted(self):
        """Unquoted, `(max-width: 767px)` is a shell subshell, not a string."""
        b = backend()
        size_mod.image_size_item_create(b, 6, "(max-width: 767px)")
        cmd = sent(b)
        assert "'(max-width: 767px)'" in cmd

    def test_item_delete_targets_the_variant_not_its_size(self):
        b = backend()
        size_mod.image_size_item_delete(b, 2)
        assert "contao:image-size-item:delete" in sent(b)


class TestGroupIsRegistered:
    def test_the_group_is_reachable_and_complete(self):
        result = CliRunner().invoke(cli, ["image-size", "--help"])
        assert result.exit_code == 0
        for sub in ("list", "read", "create", "update", "delete"):
            assert sub in result.output

    def test_create_refuses_without_a_theme(self):
        """tl_image_size.ptable is tl_theme — there is no themeless size."""
        result = CliRunner().invoke(cli, ["image-size", "create", "--name", "X"])
        assert result.exit_code != 0
        assert "--theme" in result.output

    def test_update_offers_the_bulk_options_like_every_other_entity(self):
        result = CliRunner().invoke(cli, ["image-size", "update", "--help"])
        assert result.exit_code == 0
        assert "--ids" in result.output
