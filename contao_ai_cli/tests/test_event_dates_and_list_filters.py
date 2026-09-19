"""Event dates and times as options, and --pid on the list filters (v0.30.0).

Practical test on c5, 2026-09-19: an event created without --end-date ended on
the day of the call and fell out of "upcoming events"; a time could only be set
as a raw timestamp, and "17:30" ended in a database error. The server now
derives the stored times (core-bundle v0.28.0); the CLI passes the dates and
times it is given and nothing else.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.cli import cli_event, cli_faq, cli_news, cli_newsletter
from contao_ai_cli.core.event import date_options, event_create


def backend(payload='{"status":"ok","id":1}'):
    b = MagicMock()
    b.run.return_value = {"stdout": payload, "returncode": 0, "stderr": ""}
    return b


def invoke(group, args, b, monkeypatch, module):
    monkeypatch.setattr(module, "_get_backend", lambda path: b)
    monkeypatch.setattr(module, "_require_core_bundle", lambda ctx, what: None)
    return CliRunner().invoke(group, args, obj={"session": None, "as_json": True})


class TestCreate:
    def test_no_end_date_is_sent_when_none_is_given(self):
        b = backend()
        event_create(b, "Runde", 12, "2026-10-04")
        cmd = b.run.call_args[0][0]
        assert "--startDate=2026-10-04" in cmd
        assert "--endDate" not in cmd

    def test_times_are_passed_as_given(self):
        b = backend()
        event_create(b, "Abend", 12, "2026-10-09", start_time="17:30", end_time="20:00")
        cmd = b.run.call_args[0][0]
        assert "--startTime=17:30" in cmd and "--endTime=20:00" in cmd

    def test_cli_options(self, monkeypatch):
        b = backend()
        r = invoke(cli_event.event, ["create", "--title", "Abend", "--pid", "12", "--start-date", "2026-10-09",
                                     "--start-time", "17:30", "--end-time", "20:00"], b, monkeypatch, cli_event)
        assert r.exit_code == 0, r.output
        cmd = b.run.call_args[0][0]
        assert "--startTime=17:30" in cmd and "--endTime=20:00" in cmd and "--endDate" not in cmd

    def test_help_no_longer_promises_the_start_date_as_end(self):
        r = CliRunner().invoke(cli_event.event, ["create", "--help"])
        assert "default: start date" not in r.output
        assert "--start-time" in r.output and "--end-time" in r.output


class TestUpdate:
    def test_date_option_alone_is_enough(self, monkeypatch):
        b = backend('{"status":"ok","id":23,"updated":["startDate","startTime","endTime"]}')
        r = invoke(cli_event.event, ["update", "23", "--start-date", "2026-10-11"], b, monkeypatch, cli_event)
        assert r.exit_code == 0, r.output
        cmd = b.run.call_args[0][0]
        assert cmd.startswith("contao:event:update --startDate=2026-10-11 23")
        assert "--set" not in cmd

    def test_options_and_set_together(self, monkeypatch):
        b = backend()
        r = invoke(cli_event.event, ["update", "23", "--start-time", "18:00", "--set", "location=Kahlenberg"],
                   b, monkeypatch, cli_event)
        assert r.exit_code == 0, r.output
        cmd = b.run.call_args[0][0]
        assert "--startTime=18:00" in cmd and "--set location=Kahlenberg" in cmd

    def test_bulk_carries_the_options(self, monkeypatch):
        b = backend('{"status":"ok","total":2,"succeeded":2,"failed":0,"ids":[1,2],"errors":[]}')
        r = invoke(cli_event.event, ["update", "--ids", "1,2", "--end-time", "21:00"], b, monkeypatch, cli_event)
        assert r.exit_code == 0, r.output
        cmd = b.run.call_args[0][0]
        assert "--endTime=21:00" in cmd and "--ids=1,2" in cmd

    def test_nothing_to_change_is_a_usage_error(self, monkeypatch):
        b = backend()
        r = invoke(cli_event.event, ["update", "23"], b, monkeypatch, cli_event)
        assert r.exit_code == 2
        b.run.assert_not_called()

    def test_empty_option_is_a_usage_error(self, monkeypatch):
        # Dropped silently before the review: "--end-date ''" answered like no option.
        b = backend()
        r = invoke(cli_event.event, ["update", "23", "--end-date", "", "--set", "location=x"], b, monkeypatch, cli_event)
        assert r.exit_code == 2
        assert "--set endDate=" in r.output
        b.run.assert_not_called()

    def test_values_are_quoted(self):
        assert date_options("2026-10-04; rm -rf /") == "--startDate='2026-10-04; rm -rf /'"


class TestListFiltersTakePid:
    """Create takes --pid everywhere; the lists named the same filter differently."""

    def _filter_sent(self, group, args, module, monkeypatch):
        b = backend('{"status":"ok","results":[]}')
        r = invoke(group, args, b, monkeypatch, module)
        assert r.exit_code == 0, r.output
        return b.run.call_args[0][0]

    def test_event_list(self, monkeypatch):
        assert "--filter=pid=12" in self._filter_sent(cli_event.event, ["list", "--pid", "12"], cli_event, monkeypatch)

    def test_faq_list(self, monkeypatch):
        assert "--filter=pid=12" in self._filter_sent(cli_faq.faq, ["list", "--pid", "12"], cli_faq, monkeypatch)

    def test_news_list(self, monkeypatch):
        assert "--filter=pid=20" in self._filter_sent(cli_news.news, ["list", "--pid", "20"], cli_news, monkeypatch)

    def test_newsletter_list_and_subscribers(self, monkeypatch):
        assert "--filter=pid=10" in self._filter_sent(cli_newsletter.newsletter, ["list", "--pid", "10"],
                                                      cli_newsletter, monkeypatch)
        assert "pid=10" in self._filter_sent(cli_newsletter.newsletter, ["subscribers", "--pid", "10"],
                                             cli_newsletter, monkeypatch)

    def test_old_names_still_work(self, monkeypatch):
        assert "--filter=pid=12" in self._filter_sent(cli_event.event, ["list", "--calendar", "12"], cli_event, monkeypatch)
