"""--after on page/article/content create and --offset on content find (core-bundle v1.12.0).

Through Click with the real option wiring, so a misnamed parameter shows here and not
on the server. With --after the core takes the parent from the sibling and refuses
--pid and --ptable, so the CLI must not send them -- not even their defaults.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_article import article
from contao_ai_cli.cli.cli_content import content
from contao_ai_cli.cli.cli_page import page


def _invoke(group, module: str, args: list[str]) -> tuple:
    backend = MagicMock()
    backend.run.return_value = {"stdout": json.dumps({"status": "ok", "id": 7})}
    with patch(f"contao_ai_cli.cli.{module}._require_core_bundle"), \
         patch(f"contao_ai_cli.cli.{module}._get_backend", return_value=backend):
        result = CliRunner().invoke(group, args, obj={})
    sent = backend.run.call_args.args[0] if backend.run.called else None
    return result, sent


def test_content_create_after_sends_neither_pid_nor_ptable():
    result, sent = _invoke(content, "cli_content", ["create", "--type", "text", "--after", "640", "--text", "Mitte"])

    assert result.exit_code == 0, result.output
    assert "--after=640" in sent
    assert "--pid" not in sent and "--ptable" not in sent


def test_content_create_with_pid_keeps_the_default_parent_table():
    result, sent = _invoke(content, "cli_content", ["create", "--type", "text", "--pid", "35"])

    assert result.exit_code == 0, result.output
    assert "--pid=35" in sent and "--ptable=tl_article" in sent and "--after" not in sent


def test_content_create_needs_exactly_one_of_pid_and_after():
    for args in (["create", "--type", "text"], ["create", "--type", "text", "--pid", "3", "--after", "5"]):
        result, sent = _invoke(content, "cli_content", args)
        assert result.exit_code == 2 and sent is None, args


def test_content_create_after_refuses_ptable():
    result, sent = _invoke(content, "cli_content", ["create", "--type", "text", "--after", "5", "--ptable", "tl_news"])

    assert result.exit_code == 2 and sent is None
    assert "leave out --ptable" in result.output


def test_article_create_after_sends_no_pid():
    result, sent = _invoke(article, "cli_article", ["create", "--title", "Zweiter", "--after", "2881"])

    assert result.exit_code == 0, result.output
    assert "--after=2881" in sent and "--pid" not in sent
    result, sent = _invoke(article, "cli_article", ["create", "--title", "X"])
    assert result.exit_code == 2 and sent is None


def test_page_create_after_sends_no_pid_and_without_both_stays_at_the_top():
    result, sent = _invoke(page, "cli_page", ["create", "--title", "B", "--after", "3848"])
    assert result.exit_code == 0, result.output
    assert "--after=3848" in sent and "--pid" not in sent

    result, sent = _invoke(page, "cli_page", ["create", "--title", "Root", "--type", "root"])
    assert "--pid=0" in sent

    result, sent = _invoke(page, "cli_page", ["create", "--title", "B", "--after", "3848", "--pid", "1"])
    assert result.exit_code == 2 and sent is None


def test_content_find_offset_reaches_the_command():
    result, sent = _invoke(content, "cli_content", ["find", "digital", "--limit", "50", "--offset", "50", "--json"])

    assert result.exit_code == 0, result.output
    assert sent == "contao:content:find --limit=50 --offset=50 -- digital"
    result, sent = _invoke(content, "cli_content", ["find", "digital", "--offset", "-1"])
    assert result.exit_code == 2 and sent is None
