"""
`schema palette` — issue #56.

The CLI could already answer "which fields does this kind of record have": the
server command is `contao:dca:palette` (core-bundle v0.16.0) and the CLI reached
it as `schema mandatory --set type=…`. Nobody looking for the fields of a type
searches under "mandatory", and in the guide it was the closing sentence of a
paragraph about mandatory fields.

Found on a live site on 2026-09-24: `record list tl_content --fields=html` came
back empty for an `unfiltered_html` element, because Contao has two HTML content
elements and that one stores its markup in `unfilteredHtml`. The answer was
correct and told the reader nothing.
"""
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

    def test_without_set_it_says_what_is_missing_and_where_to_go(self):
        """A table has one palette per type; answering "the palette of tl_content" is meaningless."""
        result = run(["palette", "tl_content"])
        assert result.exit_code != 0
        assert "--set type=" in result.output
        assert "schema mandatory tl_content" in result.output

    def test_it_reaches_no_server_when_the_record_is_missing(self):
        with patch("contao_ai_cli.cli.cli_schema._get_backend") as backend:
            run(["palette", "tl_content"])
        backend.assert_not_called()

    def test_the_old_spelling_still_works(self):
        """`schema mandatory --set …` is in the wild; it does not become an error."""
        with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
             patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
            mod.palette.return_value = {"status": "ok", "fields": []}
            result = run(["mandatory", "tl_content", "--set", "type=unfiltered_html"])
        assert result.exit_code == 0
        mod.palette.assert_called_once()


class TestTheGuideSaysWhyItMatters:
    def test_agents_md_names_the_two_html_elements(self):
        """The command alone does not help anyone who does not know the trap exists."""
        text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        assert "schema palette" in text
        assert "unfilteredHtml" in text and "unfiltered_html" in text

    def test_the_help_text_carries_the_example(self):
        result = run(["palette", "--help"])
        assert "unfiltered_html" in result.output
