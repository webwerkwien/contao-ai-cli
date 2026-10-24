"""A refusal names the CLI command to look a value up, not the console one (v1.6.0).

The rule: agents should not have to guess input.
core-bundle names its own console commands (`contao:dca:options tl_content type`) in a
refusal; a caller of this CLI types `contao-ai-cli schema ...`.
"""
import json
from unittest.mock import patch

from click.testing import CliRunner

from contao_ai_cli.cli import cli_schema
from contao_ai_cli.utils.contao_backend import ContaoBackend


def test_the_core_lookups_become_cli_commands():
    text = ContaoBackend.with_cli_names(
        "Available: text, headline. Look the list up with `contao:dca:options tl_content type`, "
        "the fields of a type with `contao:dca:palette tl_content --set type=<value>`. "
        "Or `contao:dca:palette tl_member`, `contao:dca:schema tl_page`."
    )
    assert "`contao-ai-cli schema sync tl_content`, then `contao-ai-cli schema resolve tl_content type`" in text
    assert "`contao-ai-cli schema palette tl_content --set type=<value>`" in text
    assert "`contao-ai-cli schema palette tl_member`" in text
    assert "`contao-ai-cli schema sync tl_page` (then `schema show tl_page`)" in text
    assert "contao:dca:" not in text


def test_the_error_of_a_command_carries_them():
    stdout = json.dumps({"status": "error", "code": 1,
                         "message": "InvalidArgumentException: Not a value Contao offers for tl_content.type: texxt. "
                                    "Look the list up with `contao:dca:options tl_content type`."})
    explained = ContaoBackend._explain_failure(stdout, "")
    assert "contao-ai-cli schema resolve tl_content type" in explained
    assert "contao:dca:options" not in explained


def test_schema_sync_says_what_its_mandatory_list_is():
    """Consho's shop table: `currency` listed as mandatory though no palette shows it."""
    with patch("contao_ai_cli.cli.cli_schema._get_backend"), \
         patch("contao_ai_cli.cli.cli_schema.dca_schema") as mod:
        mod.sync_table.return_value = {"fetched": True, "fields": {"title": {"mandatory": True}, "currency": {"mandatory": True}}}
        result = CliRunner().invoke(cli_schema.schema, ["sync", "tl_consho_shop", "--json"], obj={})
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mandatory_fields"] == ["title", "currency"], "the key callers read stays as it was"
    assert "whether or not a palette shows the field" in data["mandatory_note"]
    assert "schema palette tl_consho_shop" in data["mandatory_note"]
