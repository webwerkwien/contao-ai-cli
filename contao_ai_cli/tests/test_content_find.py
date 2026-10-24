"""`content find` (v1.12.0): content elements by their text, via core's contao:content:find.

The search index answers pages, and a page with noindex is never in it; a chat
needed 9-10 calls to find one slider headline that way.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_content import content_find_cmd
from contao_ai_cli.core.content import content_find


def _backend(answer: dict) -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps(answer), "stderr": "", "returncode": 0}
    return backend


def test_the_text_is_quoted_for_the_shell():
    backend = _backend({"status": "ok", "count": 0, "results": []})

    content_find(backend, "A powerful CMS; rm -rf /")

    assert backend.run.call_args.args[0] == "contao:content:find -- 'A powerful CMS; rm -rf /'"


def test_limit_and_root_are_passed_as_numbers():
    backend = _backend({"status": "ok", "count": 0, "results": []})

    content_find(backend, "Über uns", limit=5, root=12)

    assert backend.run.call_args.args[0] == "contao:content:find --limit=5 --root=12 -- 'Über uns'"


def test_the_answer_comes_through():
    hit = {"id": 160, "root": {"id": 2, "language": "en"}}
    backend = _backend({"status": "ok", "count": 1, "results": [hit]})

    with patch("contao_ai_cli.cli.cli_content._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_content._get_backend", return_value=backend):
        result = CliRunner().invoke(content_find_cmd, ["powerful", "--json"], obj={})

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["results"] == [hit]


def test_a_text_starting_with_a_dash_is_not_an_option():
    backend = _backend({"status": "ok", "count": 0, "results": []})

    content_find(backend, "-20% Rabatt")

    assert backend.run.call_args.args[0] == "contao:content:find -- '-20% Rabatt'"


def test_the_options_reach_the_command_through_click():
    backend = _backend({"status": "ok", "count": 0, "results": []})

    with patch("contao_ai_cli.cli.cli_content._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_content._get_backend", return_value=backend):
        result = CliRunner().invoke(content_find_cmd, ["Team", "--limit", "5", "--root", "12", "--json"], obj={})

    assert result.exit_code == 0, result.output
    assert backend.run.call_args.args[0] == "contao:content:find --limit=5 --root=12 -- Team"
