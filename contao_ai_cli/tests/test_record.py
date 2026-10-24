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


class TestRecordClone:
    """`record clone` passes the table through; the server decides what has a cloner."""

    @staticmethod
    def clone_backend():
        b = MagicMock()
        b.run.return_value = {"stdout": '{"status": "ok", "id": 9}'}
        return b

    def test_recipients_are_not_asked_for_unless_given(self):
        """Recipients consented to the source channel (core-bundle v1.8.0)."""
        b = self.clone_backend()
        record_mod.record_clone(b, "tl_newsletter_channel", 3)
        assert "--with-recipients" not in b.run.call_args[0][0]

    def test_with_recipients_reaches_the_server(self):
        b = self.clone_backend()
        record_mod.record_clone(b, "tl_newsletter_channel", 3, with_recipients=True)
        cmd = b.run.call_args[0][0]
        assert cmd.startswith("contao:record:clone --source-table=tl_newsletter_channel --source-id=3")
        assert "--with-recipients" in cmd

    def test_the_command_passes_the_flag_and_the_operator_where_they_belong(self, monkeypatch):
        """Through Click, not around it: a swapped argument would send --operator=True."""
        from contao_ai_cli.cli import cli_record

        b = self.clone_backend()
        monkeypatch.setattr(cli_record, "_get_backend", lambda path: b)
        monkeypatch.setattr(cli_record, "_require_core_bundle", lambda ctx, what: None)

        result = CliRunner().invoke(cli_record.record, [
            "clone", "--source-table", "tl_newsletter_channel", "--source-id", "3",
            "--with-recipients", "--yes", "--operator", "k.jones",
        ], obj={"session": None, "as_json": True})

        assert result.exit_code == 0, result.output
        cmd = b.run.call_args[0][0]
        assert "--with-recipients" in cmd
        assert "--operator=k.jones" in cmd

        b.run.reset_mock()
        CliRunner().invoke(cli_record.record, [
            "clone", "--source-table", "tl_newsletter_channel", "--source-id", "3",
        ], obj={"session": None, "as_json": True})
        assert "--with-recipients" not in b.run.call_args[0][0]

    def test_the_flag_is_on_the_command(self):
        result = CliRunner().invoke(cli, ["record", "clone", "--help"])
        assert "--with-recipients" in result.output
        assert "tl_form" in result.output

    @staticmethod
    def invoke_with_recipients(monkeypatch, extra=(), console=False, answer=None, table="tl_newsletter_channel"):
        """`record clone --with-recipients` through Click; returns (result, backend)."""
        from contao_ai_cli.cli import cli_record, helpers

        b = TestRecordClone.clone_backend()
        monkeypatch.setattr(cli_record, "_get_backend", lambda path: b)
        monkeypatch.setattr(cli_record, "_require_core_bundle", lambda ctx, what: None)
        monkeypatch.setattr(helpers, "stdin_is_console", lambda: console)
        monkeypatch.setattr(helpers, "ask_yes_no", lambda question, default=False: answer)
        result = CliRunner().invoke(cli_record.record, [
            "clone", "--source-table", table, "--source-id", "3", "--with-recipients", *extra,
        ], obj={"session": None, "as_json": True})
        return result, b

    def test_without_a_terminal_recipients_need_yes(self, monkeypatch):
        """An agent has no terminal: it asks the operator in its chat, then passes --yes (v1.10.0)."""
        result, b = self.invoke_with_recipients(monkeypatch)
        assert result.exit_code != 0
        assert "Nothing was cloned" in result.output
        b.run.assert_not_called()

    def test_a_person_at_a_terminal_answers(self, monkeypatch):
        result, b = self.invoke_with_recipients(monkeypatch, console=True, answer=True)
        assert result.exit_code == 0, result.output
        assert "--with-recipients" in b.run.call_args[0][0]

        result, b = self.invoke_with_recipients(monkeypatch, console=True, answer=False)
        assert result.exit_code != 0
        b.run.assert_not_called()

        # Nobody at the terminal after all (EOF): a no, not a quiet clone without them.
        result, b = self.invoke_with_recipients(monkeypatch, console=True, answer=None)
        assert result.exit_code != 0
        b.run.assert_not_called()

    def test_recipients_for_another_table_are_refused_before_asking(self, monkeypatch):
        """No --yes, a terminal nobody answers: asked first, it would end in "Nothing was
        cloned" — the table refusal proves it comes before the question."""
        result, b = self.invoke_with_recipients(monkeypatch, console=True, answer=None, table="tl_form")
        assert result.exit_code != 0
        assert "tl_newsletter_channel only" in result.output
        b.run.assert_not_called()


class TestBridgeCloneRecipients:
    """`bridge clone` takes recipients too (v1.10.0); the CLI asks, the server does not again."""

    @staticmethod
    def invoke(monkeypatch, args, answer_payload=None):
        from contao_ai_cli.cli import cli_bridge, helpers

        client = MagicMock()
        # The shape the bridge really answers with: the core's answer
        # sits under "result".
        client.clone.return_value = answer_payload if answer_payload is not None else {
            "status": "ok", "tool": "record_clone",
            "result": {"status": "ok", "id": 20, "table": "tl_newsletter_channel", "recipients_copied": True}}
        monkeypatch.setattr(cli_bridge.session_mod, "load_session", lambda path: {})
        monkeypatch.setattr(cli_bridge.bridge_mod, "from_session_config", lambda cfg: client)
        monkeypatch.setattr(helpers, "stdin_is_console", lambda: False)
        result = CliRunner().invoke(cli_bridge.bridge, ["clone", *args], obj={"session": None, "as_json": True})
        return result, client

    def test_yes_sends_the_flag(self, monkeypatch):
        result, client = self.invoke(monkeypatch, ["--table", "tl_newsletter_channel", "--source-id", "4",
                                                   "--with-recipients", "--yes"])
        assert result.exit_code == 0, result.output
        assert client.clone.call_args.kwargs["with_recipients"] is True
        assert "warning" not in result.output.lower()

    def test_without_yes_and_terminal_nothing_is_sent(self, monkeypatch):
        result, client = self.invoke(monkeypatch, ["--table", "tl_newsletter_channel", "--source-id", "4",
                                                   "--with-recipients"])
        assert result.exit_code != 0
        client.clone.assert_not_called()

    def test_an_older_backend_that_drops_the_flag_is_reported(self, monkeypatch):
        result, client = self.invoke(monkeypatch, ["--table", "tl_newsletter_channel", "--source-id", "4",
                                                   "--with-recipients", "--yes"],
                                     answer_payload={"status": "ok", "tool": "record_clone",
                                                     "result": {"status": "ok", "id": 20}})
        assert result.exit_code == 0
        assert "the clone has no recipients" in result.output

    def test_the_payload_carries_the_key_only_when_asked(self):
        from contao_ai_cli.core import backend_bridge

        client = backend_bridge.BackendBridgeClient.__new__(backend_bridge.BackendBridgeClient)
        sent = []
        client._call = lambda payload: sent.append(payload) or {}
        client.clone("tl_newsletter_channel", 4)
        client.clone("tl_newsletter_channel", 4, with_recipients=True)
        assert "withRecipients" not in sent[0]
        assert sent[1]["withRecipients"] is True
