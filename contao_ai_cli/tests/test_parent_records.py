"""
The three parent records — news archive, calendar, FAQ category.

The same gap three times over: `news create`, `event create` and `faq create`
all took a `--pid`, and the record that pid pointed at could not be created.
**The child worked, the parent did not**, so the first news item on a fresh
install still meant opening the back end.

They live inside the existing groups rather than in three groups of their own,
next to the listings that were already there (`news archives`, `event
calendars`, `faq categories`) — the same shape as `image-size item-*`.

What is pinned here is the command strings. The requirement rules —
`jumpTo` always, `groups` only for a protected record, `headline` instead of
`jumpTo` for a category — are DCA-driven and live in the bundle. Duplicating
them here would put the same decision in two places, which is exactly what the
bundle's shared `missingMandatoryFields()` was introduced to stop.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import event as event_mod
from contao_ai_cli.core import faq as faq_mod
from contao_ai_cli.core import news as news_mod


def backend():
    b = MagicMock()
    b.run.return_value = {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""}
    b.run_json.return_value = {"status": "ok"}
    return b


def sent(b) -> str:
    if b.run_json.called:
        return b.run_json.call_args[0][0]
    return b.run.call_args[0][0]


class TestNewsArchive:
    def test_read_uses_the_dedicated_command(self):
        b = backend()
        news_mod.news_archive_read(b, 3)
        assert sent(b) == "contao:news-archive:read 3"

    def test_create_passes_the_title_and_the_extra_fields(self):
        b = backend()
        news_mod.news_archive_create(b, "Blog", {"jumpTo": "7"})
        cmd = sent(b)
        assert cmd.startswith("contao:news-archive:create")
        assert "--title=Blog" in cmd
        assert "jumpTo=7" in cmd

    def test_create_does_not_invent_a_jump_to(self):
        """The requirement is the bundle's to enforce — the CLI must not quietly
        fill it in, or a missing target would become a wrong one."""
        b = backend()
        news_mod.news_archive_create(b, "Blog")
        assert "jumpTo" not in sent(b)

    def test_update_and_delete_use_the_dedicated_commands(self):
        b = backend()
        news_mod.news_archive_update(b, 3, {"title": "x"})
        assert "contao:news-archive:update" in sent(b)

        b = backend()
        news_mod.news_archive_delete(b, 3)
        assert "contao:news-archive:delete" in sent(b)


class TestCalendar:
    def test_read_create_update_delete_use_the_dedicated_commands(self):
        for call, expected in (
            (lambda b: event_mod.calendar_read(b, 2), "contao:calendar:read"),
            (lambda b: event_mod.calendar_create(b, "Touren"), "contao:calendar:create"),
            (lambda b: event_mod.calendar_update(b, 2, {"title": "x"}), "contao:calendar:update"),
            (lambda b: event_mod.calendar_delete(b, 2), "contao:calendar:delete"),
        ):
            b = backend()
            call(b)
            assert expected in sent(b)

    def test_a_title_with_spaces_survives_the_shell(self):
        b = backend()
        event_mod.calendar_create(b, "Wiener Wandern")
        assert "'Wiener Wandern'" in sent(b)


class TestFaqCategory:
    def test_read_create_update_delete_use_the_dedicated_commands(self):
        for call, expected in (
            (lambda b: faq_mod.faq_category_read(b, 1), "contao:faq-category:read"),
            (lambda b: faq_mod.faq_category_create(b, "Support"), "contao:faq-category:create"),
            (lambda b: faq_mod.faq_category_update(b, 1, {"title": "x"}), "contao:faq-category:update"),
            (lambda b: faq_mod.faq_category_delete(b, 1), "contao:faq-category:delete"),
        ):
            b = backend()
            call(b)
            assert expected in sent(b)

    def test_the_headline_is_passed_through_as_a_field(self):
        """`title` is the back end label, `headline` the heading on the page.
        Nothing derives one from the other."""
        b = backend()
        faq_mod.faq_category_create(b, "Support", {"headline": "Frequently asked"})
        cmd = sent(b)
        assert "--title=Support" in cmd
        assert "headline=Frequently asked" in cmd


class TestRegistration:
    """A command nobody can reach is the failure this project already had once."""

    def test_the_parent_subcommands_sit_in_their_existing_groups(self):
        for group, prefix in (("news", "archive"), ("event", "calendar"), ("faq", "category")):
            result = CliRunner().invoke(cli, [group, "--help"])
            assert result.exit_code == 0
            for verb in ("read", "create", "update", "delete"):
                assert f"{prefix}-{verb}" in result.output, f"{group} {prefix}-{verb} missing"

    def test_the_existing_listings_are_untouched(self):
        """`news archives` and friends predate this and keep their names."""
        for group, listing in (("news", "archives"), ("event", "calendars"), ("faq", "categories")):
            result = CliRunner().invoke(cli, [group, "--help"])
            assert listing in result.output
