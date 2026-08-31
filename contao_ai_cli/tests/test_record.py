"""
The generic table group.

`contao:record:list` and `contao:dca:schema` have been in the core bundle since
its early releases, but their only caller was RecordListTool / MetaTool in
contao-ai-backend-bundle: they were built for the browser chat, and this CLI
never reached for them. Every table without a dedicated group — tl_image_size,
tl_theme, tl_module, anything a third-party extension registers — was therefore
unreachable from here, while the command that could read it sat on the server
being used by something else.

These tests pin the command string, because that string is the whole contract:
the module deliberately validates nothing itself. The server checks the table,
the columns, the sort keys and the filters against the live DCA and answers with
a structured error. Duplicating those rules on this side would create a second
place to keep in sync — the exact cost the backend bundle already carries in
RecordListTool::TABLE_MODULE, which its own comment asks callers to remember to
update in two places.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import record as record_mod


def backend():
    b = MagicMock()
    b.run_json.return_value = {"status": "ok", "results": []}
    return b


def sent(b) -> str:
    return b.run_json.call_args[0][0]


class TestRecordList:
    def test_the_bare_call_passes_only_the_table(self):
        b = backend()
        record_mod.record_list(b, "tl_image_size")
        assert sent(b) == "contao:record:list tl_image_size"

    def test_no_option_is_sent_when_it_was_not_given(self):
        """Server-side defaults have to stay in charge — limit 20, order id DESC."""
        b = backend()
        record_mod.record_list(b, "tl_page")
        cmd = sent(b)
        for option in ("--limit", "--offset", "--order", "--fields", "--filter"):
            assert option not in cmd

    def test_every_option_reaches_the_server(self):
        b = backend()
        record_mod.record_list(
            b, "tl_page", limit=50, offset=10, order="tstamp DESC",
            filters=("published=1", "type=regular"), fields="id,title",
        )
        cmd = sent(b)
        assert "--limit 50" in cmd
        assert "--offset 10" in cmd
        # Quoted, because the space would otherwise split the argument.
        assert "--order 'tstamp DESC'" in cmd
        # Not quoted: shlex.quote only quotes when it has to, and neither a
        # comma nor an `=` is special to the shell.
        assert "--fields id,title" in cmd
        assert "--filter published=1" in cmd
        assert "--filter type=regular" in cmd

    def test_filters_repeat_rather_than_join(self):
        b = backend()
        record_mod.record_list(b, "tl_news", filters=("pid=5", "published=1"))
        assert sent(b).count("--filter") == 2

    def test_arguments_are_quoted(self):
        """A table name and an order clause are user input and reach a shell."""
        b = backend()
        record_mod.record_list(b, "tl_page; rm -rf /", order="id DESC")
        cmd = sent(b)
        assert "; rm -rf /" not in cmd.replace("'tl_page; rm -rf /'", "")

    def test_numeric_options_are_coerced(self):
        """Click types them, but the module is callable on its own too."""
        b = backend()
        record_mod.record_list(b, "tl_page", limit="50", offset="0")
        assert "--limit 50" in sent(b)

    def test_zero_offset_is_still_sent(self):
        """`is not None`, not truthiness — offset 0 is a legitimate value."""
        b = backend()
        record_mod.record_list(b, "tl_page", offset=0)
        assert "--offset 0" in sent(b)


class TestDcaSchema:
    def test_it_calls_the_core_bundles_own_json_command(self):
        """Not `debug:dca` — that is the text output the `schema` group parses."""
        b = backend()
        record_mod.dca_schema(b, "tl_image_size")
        assert sent(b) == "contao:dca:schema tl_image_size"


class TestRecordGroupIsRegistered:
    def test_the_group_is_reachable_from_the_root_command(self):
        """The regression this whole change is about: built, but never wired up."""
        result = CliRunner().invoke(cli, ["record", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "schema" in result.output

    def test_list_requires_a_table(self):
        result = CliRunner().invoke(cli, ["record", "list"])
        assert result.exit_code != 0
