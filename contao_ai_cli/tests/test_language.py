"""The language group sends the core's changelanguage commands (core-bundle v1.4.0)."""
import json
from unittest.mock import MagicMock

from contao_ai_cli.core import language as language_mod


def _backend(answer: dict) -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps(answer)}
    return backend


def test_link_sends_table_id_and_main():
    backend = _backend({"status": "ok", "field": "languageMain"})

    result = language_mod.language_link(backend, "tl_page", 85, 73)

    backend.run.assert_called_once_with("contao:language:link --table tl_page --id 85 --main 73")
    assert result["field"] == "languageMain"


def test_link_with_main_zero_removes_the_link():
    backend = _backend({"status": "ok"})

    language_mod.language_link(backend, "tl_news_archive", 7, 0)

    backend.run.assert_called_once_with("contao:language:link --table tl_news_archive --id 7 --main 0")


def test_check_without_and_with_a_root():
    backend = _backend({"status": "ok", "roots": []})

    language_mod.language_check(backend)
    language_mod.language_check(backend, 83)

    assert [c.args[0] for c in backend.run.call_args_list] == [
        "contao:language:check",
        "contao:language:check --root 83",
    ]


def test_versions_sends_table_and_id_as_arguments():
    backend = _backend({"status": "ok", "linked": True, "versions": [{"id": 102, "language": "de"}]})

    result = language_mod.language_versions(backend, "tl_article", 36)

    backend.run.assert_called_once_with("contao:language:versions tl_article 36")
    assert result["versions"][0]["language"] == "de"


def test_versions_command_is_offered_with_its_tables():
    from click.testing import CliRunner
    from contao_ai_cli.cli.cli_language import language

    out = CliRunner().invoke(language, ["versions", "--help"]).output

    assert "tl_calendar_events" in out and "tl_news_archive" not in out


def test_an_answer_that_is_no_json_comes_back_raw():
    backend = MagicMock()
    backend.run.return_value = {"stdout": "not json"}

    assert language_mod.language_check(backend) == {"raw": "not json"}
