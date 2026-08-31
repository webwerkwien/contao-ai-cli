"""
The module group.

`tl_module` is the largest table of the theme layer and the one where "what do I
have to supply" has no single answer: twelve fields are mandatory in the DCA,
but each applies only to the module types whose palette contains it. That
resolution lives on the server, computed from the DCA, so nothing here carries a
copy of it — these tests pin that nothing here tries to.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import module as module_mod


def backend():
    b = MagicMock()
    b.run.return_value = {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""}
    b.run_json.return_value = {"status": "ok"}
    return b


def sent(b) -> str:
    if b.run_json.called:
        return b.run_json.call_args[0][0]
    return b.run.call_args[0][0]


class TestTypes:
    def test_types_asks_the_server_rather_than_answering_itself(self):
        """The mapping lives in the DCA; a copy here would drift and would miss
        every module type an extension registers."""
        b = backend()
        module_mod.module_types(b)
        assert sent(b) == "contao:module:types"


class TestList:
    def test_it_goes_through_the_generic_record_command(self):
        b = backend()
        module_mod.module_list(b)
        assert sent(b).startswith("contao:record:list tl_module")

    def test_type_is_listed_because_it_decides_what_the_rest_means(self):
        assert "type" in module_mod.LIST_FIELDS.split(",")

    def test_both_filters_can_be_combined(self):
        b = backend()
        module_mod.module_list(b, theme_id=1, module_type="newslist")
        cmd = sent(b)
        assert "--filter pid=1" in cmd
        assert "--filter type=newslist" in cmd

    def test_the_limit_is_raised_because_a_theme_holds_dozens(self):
        """41 modules on the demo install alone; the server default of 20 would
        silently show half a theme."""
        b = backend()
        module_mod.module_list(b)
        assert "--limit 100" in sent(b)


class TestWriteCommands:
    def test_create_passes_theme_name_and_type(self):
        b = backend()
        module_mod.module_create(b, 1, "News - Latest", "newslist")
        cmd = sent(b)
        assert "--pid=1" in cmd
        assert "--type=newslist" in cmd
        assert "News - Latest" in cmd

    def test_create_passes_type_specific_fields_untouched(self):
        """The comma list is the server's to interpret — it knows which fields
        are multi-value, this side does not."""
        b = backend()
        module_mod.module_create(b, 1, "N", "newslist",
                                 {"news_archives": "1,3", "numberOfItems": "5"})
        cmd = sent(b)
        assert "news_archives=1,3" in cmd or "'news_archives=1,3'" in cmd
        assert "numberOfItems=5" in cmd

    def test_update_and_delete_reach_their_commands(self):
        b = backend()
        module_mod.module_update(b, 67, {"numberOfItems": "8"})
        assert "contao:module:update" in sent(b)

        b = backend()
        module_mod.module_delete(b, 67)
        assert "contao:module:delete" in sent(b)


class TestGroupIsRegistered:
    def test_the_group_is_reachable_and_complete(self):
        result = CliRunner().invoke(cli, ["module", "--help"])
        assert result.exit_code == 0
        for sub in ("types", "list", "read", "create", "update", "delete"):
            assert sub in result.output

    def test_create_refuses_without_a_type(self):
        result = CliRunner().invoke(cli, ["module", "create", "--theme", "1", "--name", "X"])
        assert result.exit_code != 0
        assert "--type" in result.output
