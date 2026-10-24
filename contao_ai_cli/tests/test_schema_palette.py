"""
`schema palette` — issue #56.

The CLI could already answer "which fields does this kind of record have": the
server command is `contao:dca:palette` (core-bundle v0.16.0) and the CLI reached
it as `schema mandatory --set type=…`. Nobody looking for the fields of a type
searches under "mandatory", and in the guide it was the closing sentence of a
paragraph about mandatory fields.

Found on a live site: `record list tl_content --fields=html` came
back empty for an `unfiltered_html` element, because Contao has two HTML content
elements and that one stores its markup in `unfilteredHtml`. The answer was
correct and told the reader nothing.
"""
import json
import pathlib
from unittest.mock import patch

from click.testing import CliRunner

from contao_ai_cli.cli import cli_schema

REPO = pathlib.Path(__file__).resolve().parent.parent.parent


def run(args):
    return CliRunner().invoke(cli_schema.schema, args, obj={})


class TestTheCommandExists:
    def test_it_asks_the_server_for_the_palette_of_that_record(self):
        with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
             patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
            mod.palette.return_value = {"status": "ok", "fields": ["type", "unfilteredHtml"]}
            result = run(["palette", "tl_content", "--set", "type=unfiltered_html"])
        assert result.exit_code == 0, result.output
        assert mod.palette.call_args[0][1] == "tl_content"
        assert mod.palette.call_args[0][2] == {"type": "unfiltered_html"}

    def test_it_is_the_same_answer_as_schema_mandatory_with_set(self):
        """One implementation. Two that could drift is one too many."""
        calls = []
        for command in (["palette", "tl_page", "--set", "type=root"],
                        ["mandatory", "tl_page", "--set", "type=root"]):
            with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
                 patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
                mod.palette.return_value = {"status": "ok", "fields": []}
                run(command)
                calls.append(mod.palette.call_args[0][1:])
        assert calls[0] == calls[1]

    def test_without_set_a_typed_table_says_which_value_is_missing(self):
        """Changed in v1.6.0: `schema palette` without --set is allowed.

        Until then this refused without asking the server. A typed table answers its
        selector alone (`tl_content`: ["type"]); the answer then says what to pass.
        """
        with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
             patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
            mod.palette.return_value = {"status": "ok", "table": "tl_content", "fields": ["type"], "mandatory": []}
            result = run(["palette", "tl_content", "--json"])
        assert result.exit_code == 0, result.output
        mod.palette.assert_called_once()
        assert mod.palette.call_args.args[1:] == ("tl_content", {})
        assert "chooses its palette by type" in result.output
        assert "schema palette tl_content --set type=<value>" in result.output
        assert "schema resolve tl_content type" in result.output

    def test_without_set_a_table_without_types_gets_its_palette(self):
        """`schema palette tl_member` used to need `--set type=default`."""
        with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
             patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
            mod.palette.return_value = {"status": "ok", "table": "tl_member", "fields": ["firstname", "lastname", "email"], "mandatory": ["email"]}
            result = run(["palette", "tl_member", "--json"])
        assert result.exit_code == 0, result.output
        assert "firstname" in result.output
        assert "hint" not in result.output

    def test_the_selectors_the_server_names_win(self):
        """A core that names the missing selectors is believed over the one-field guess."""
        with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
             patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
            mod.palette.return_value = {"status": "ok", "fields": ["effect", "title"], "selectors": ["effect"]}
            result = run(["palette", "tl_consho_cart_rule", "--json"])
        assert result.exit_code == 0, result.output
        assert "chooses its palette by effect" in json.loads(result.output)["hint"]

    def test_an_empty_selector_list_is_believed_over_a_one_field_palette(self):
        """A real one-field palette got "chooses its palette by title"."""
        with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
             patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
            mod.palette.return_value = {"status": "ok", "fields": ["title"], "mandatory": ["title"], "selectors": []}
            result = run(["palette", "tl_acme_tag", "--json"])
        assert result.exit_code == 0, result.output
        assert "hint" not in json.loads(result.output)

    def test_the_old_spelling_still_works(self):
        """`schema mandatory --set …` is in the wild; it does not become an error."""
        with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
             patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
            mod.palette.return_value = {"status": "ok", "fields": []}
            result = run(["mandatory", "tl_content", "--set", "type=unfiltered_html"])
        assert result.exit_code == 0
        mod.palette.assert_called_once()


class TestTheGuideSaysWhyItMatters:
    def test_guide_names_the_two_html_elements(self):
        """The command alone does not help anyone who does not know the trap exists."""
        text = (REPO / "GUIDE.md").read_text(encoding="utf-8")
        assert "schema palette" in text
        assert "unfilteredHtml" in text and "unfiltered_html" in text

    def test_the_help_text_carries_the_example(self):
        result = run(["palette", "--help"])
        assert "unfiltered_html" in result.output
