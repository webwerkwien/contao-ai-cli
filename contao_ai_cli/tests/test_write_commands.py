"""
The update/delete/publish surface added in v0.5.0.

The core bundle had these commands from the start; the CLI only ever wrapped
create and read for content entities, so `page update` and friends did not exist
while the docs said they did. These tests pin what each wrapper actually sends.
"""
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from contao_ai_cli.cli import cli_page
from contao_ai_cli.cli.helpers import confirm_delete, parse_set_fields
from contao_ai_cli.core import article, comment, content, event, faq, news, page
from contao_ai_cli.core.contao_ops import run_delete, run_publish, run_update


def backend():
    b = MagicMock()
    b.run.return_value = {"stdout": '{"status":"ok"}'}
    return b


def sent(b):
    return b.run.call_args[0][0]


class TestGenericOperations:
    def test_update_puts_the_id_first_and_fields_as_set(self):
        b = backend()
        run_update(b, "contao:page:update", 12, {"title": "Home"})
        assert sent(b) == "contao:page:update 12 --set title=Home --no-interaction"

    def test_update_shell_quotes_dangerous_values(self):
        import shlex
        value = "O'Hara & Sons; rm -rf /"
        b = backend()
        run_update(b, "contao:news:update", 3, {"headline": value})
        cmd = sent(b)
        assert shlex.quote(f"headline={value}") in cmd
        # The payload appears only inside the quoted argument, never bare.
        assert "; rm -rf /" not in cmd.replace(shlex.quote(f"headline={value}"), "")

    def test_a_non_numeric_id_is_refused_before_the_shell(self):
        """int() is the guard: an injected id raises instead of reaching the shell."""
        b = backend()
        with pytest.raises(ValueError):
            run_update(b, "contao:page:update", "12; DROP", {"a": "b"})
        b.run.assert_not_called()

        with pytest.raises(ValueError):
            run_delete(b, "contao:page:delete", "1 OR 1=1")
        b.run.assert_not_called()

    def test_delete_is_non_interactive(self):
        b = backend()
        run_delete(b, "contao:page:delete", 7)
        assert sent(b) == "contao:page:delete 7 --no-interaction"

    def test_publish_maps_the_boolean_to_the_action_argument(self):
        b = backend()
        run_publish(b, "contao:page:publish", 4, True)
        assert sent(b) == "contao:page:publish 4 publish --no-interaction"
        run_publish(b, "contao:page:publish", 4, False)
        assert sent(b) == "contao:page:publish 4 unpublish --no-interaction"


@pytest.mark.parametrize(
    "fn, expected",
    [
        (lambda b: page.page_update(b, 1, {"a": "b"}), "contao:page:update"),
        (lambda b: page.page_delete(b, 1), "contao:page:delete"),
        (lambda b: page.page_publish(b, 1), "contao:page:publish"),
        (lambda b: article.article_update(b, 1, {"a": "b"}), "contao:article:update"),
        (lambda b: article.article_delete(b, 1), "contao:article:delete"),
        (lambda b: content.content_update(b, 1, {"a": "b"}), "contao:content:update"),
        (lambda b: content.content_delete(b, 1), "contao:content:delete"),
        (lambda b: news.news_update(b, 1, {"a": "b"}), "contao:news:update"),
        (lambda b: news.news_delete(b, 1), "contao:news:delete"),
        (lambda b: news.news_repair_headlines(b), "contao:news:repair-headlines"),
        (lambda b: event.event_update(b, 1, {"a": "b"}), "contao:event:update"),
        (lambda b: event.event_delete(b, 1), "contao:event:delete"),
        (lambda b: faq.faq_update(b, 1, {"a": "b"}), "contao:faq:update"),
        (lambda b: faq.faq_delete(b, 1), "contao:faq:delete"),
        (lambda b: comment.comment_delete(b, 1), "contao:comment:delete"),
        (lambda b: comment.comment_publish(b, 1), "contao:comment:publish"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_wrapper_targets_the_right_console_command(fn, expected):
    b = backend()
    fn(b)
    assert sent(b).startswith(expected)


class TestParseSetFields:
    def test_splits_on_the_first_equals_only(self):
        """A value may contain '=' — a query string, a base64 payload."""
        assert parse_set_fields(["url=a?b=c"]) == {"url": "a?b=c"}

    def test_accepts_an_empty_value(self):
        assert parse_set_fields(["teaser="]) == {"teaser": ""}

    def test_rejects_a_missing_equals(self):
        """Dropping it silently would report a successful update that changed nothing."""
        with pytest.raises(click.UsageError):
            parse_set_fields(["title Neu"])

    def test_rejects_a_missing_field_name(self):
        with pytest.raises(click.UsageError):
            parse_set_fields(["=value"])


class TestConfirmDelete:
    def test_yes_flag_skips_the_prompt(self):
        with patch("contao_ai_cli.cli.helpers.click.confirm") as confirm:
            assert confirm_delete("page 1", assume_yes=True) is True
        confirm.assert_not_called()

    def test_without_a_terminal_it_proceeds(self):
        """Agents, cron and CI have no one to answer; a prompt would just hang."""
        with patch("contao_ai_cli.cli.helpers.sys.stdin") as stdin, \
             patch("contao_ai_cli.cli.helpers.click.confirm") as confirm:
            stdin.isatty.return_value = False
            assert confirm_delete("page 1") is True
        confirm.assert_not_called()

    def test_on_a_terminal_it_asks_and_defaults_to_no(self):
        with patch("contao_ai_cli.cli.helpers.sys.stdin") as stdin, \
             patch("contao_ai_cli.cli.helpers.click.confirm", return_value=False) as confirm:
            stdin.isatty.return_value = True
            assert confirm_delete("page 1") is False
        assert confirm.call_args.kwargs["default"] is False


class TestDeleteCommandWiring:
    def _run(self, args, confirmed):
        with patch("contao_ai_cli.cli.cli_page._require_core_bundle"), \
             patch("contao_ai_cli.cli.cli_page._get_backend"), \
             patch("contao_ai_cli.cli.cli_page.confirm_delete", return_value=confirmed), \
             patch("contao_ai_cli.cli.cli_page.page_mod") as mod:
            result = CliRunner().invoke(cli_page.page, args, obj={})
        return result, mod

    def test_declining_deletes_nothing(self):
        result, mod = self._run(["delete", "12"], confirmed=False)
        mod.page_delete.assert_not_called()
        assert result.exit_code != 0

    def test_confirming_deletes(self):
        result, mod = self._run(["delete", "12"], confirmed=True)
        mod.page_delete.assert_called_once()
        assert mod.page_delete.call_args[0][1] == 12

    def test_yes_is_passed_through_to_the_guard(self):
        with patch("contao_ai_cli.cli.cli_page._require_core_bundle"), \
             patch("contao_ai_cli.cli.cli_page._get_backend"), \
             patch("contao_ai_cli.cli.cli_page.confirm_delete", return_value=True) as guard, \
             patch("contao_ai_cli.cli.cli_page.page_mod"):
            CliRunner().invoke(cli_page.page, ["delete", "12", "--yes"], obj={})
        assert guard.call_args[0][1] is True

    def test_update_requires_at_least_one_set(self):
        result = CliRunner().invoke(cli_page.page, ["update", "12"], obj={})
        assert result.exit_code != 0
        assert "--set" in result.output
