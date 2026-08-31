"""
The newsletter, write half — the last read-only module in the back end menu.

Three tables (tl_newsletter_channel, tl_newsletter, tl_newsletter_recipients)
and one thing this CLI deliberately will not do. The command strings are the
contract with the bundle, so they are what is pinned; the DCA rules behind them
(mandatory fields, deny list, address validation) live in the bundle and are
tested there.

Two decisions from 2026-08-31 are load-bearing here and are tested as such:

  * `newsletter send` is registered and always refuses. "No such command" reads
    like a gap, and an agent that sees a gap looks for a way around it — the
    nearest one being `sent=1`, which publishes without sending.
  * `subscriber-create` without --active/--inactive creates an INACTIVE
    recipient anywhere there is no terminal to answer. Getting that default
    backwards would look like a safeguard and wave everything through in the
    setting this CLI usually runs in.
"""
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.cli.helpers import confirm_escalation
from contao_ai_cli.core import newsletter as newsletter_mod


def backend():
    b = MagicMock()
    b.run.return_value = {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""}
    b.run_json.return_value = {"status": "ok"}
    return b


def sent(b) -> str:
    if b.run_json.called:
        return b.run_json.call_args[0][0]
    return b.run.call_args[0][0]


class TestChannel:
    def test_create_passes_the_title(self):
        b = backend()
        newsletter_mod.channel_create(b, "Kundeninfo")
        cmd = sent(b)
        assert cmd.startswith("contao:newsletter-channel:create")
        assert "--title=Kundeninfo" in cmd

    def test_the_sender_travels_as_a_set_field(self):
        """It is mandatory, but it is not an option of its own — the DCA says
        which fields are required and the bundle reports them."""
        b = backend()
        newsletter_mod.channel_create(b, "Kundeninfo", {"sender": "info@example.com"})
        assert "sender=info@example.com" in sent(b)

    def test_update_and_delete_use_the_dedicated_commands(self):
        for call, expected in (
            (lambda b: newsletter_mod.channel_update(b, 3, {"title": "x"}),
             "contao:newsletter-channel:update"),
            (lambda b: newsletter_mod.channel_delete(b, 3),
             "contao:newsletter-channel:delete"),
        ):
            b = backend()
            call(b)
            assert expected in sent(b)


class TestNewsletter:
    def test_create_sends_subject_and_channel(self):
        b = backend()
        newsletter_mod.newsletter_create(b, "Juni-Ausgabe", 1)
        cmd = sent(b)
        assert cmd.startswith("contao:newsletter:create")
        assert "--pid=1" in cmd
        assert "--subject=Juni-Ausgabe" in cmd

    def test_update_and_delete_use_the_dedicated_commands(self):
        for call, expected in (
            (lambda b: newsletter_mod.newsletter_update(b, 7, {"subject": "x"}),
             "contao:newsletter:update"),
            (lambda b: newsletter_mod.newsletter_delete(b, 7),
             "contao:newsletter:delete"),
        ):
            b = backend()
            call(b)
            assert expected in sent(b)


class TestRecipient:
    def test_create_sends_address_and_channel(self):
        b = backend()
        newsletter_mod.subscriber_create(b, "leser@example.com", 1)
        cmd = sent(b)
        assert cmd.startswith("contao:newsletter-recipient:create")
        assert "--pid=1" in cmd
        assert "--email=leser@example.com" in cmd

    def test_inactive_is_the_absence_of_the_flag(self):
        """The bundle defaults to inactive, so silence must not send --active."""
        b = backend()
        newsletter_mod.subscriber_create(b, "leser@example.com", 1, active=False)
        assert "--active" not in sent(b)

    def test_active_is_passed_when_asked_for(self):
        b = backend()
        newsletter_mod.subscriber_create(b, "leser@example.com", 1, active=True)
        assert "--active" in sent(b)


class TestTheActiveQuestion:
    """The escalation prompt and, more importantly, its headless answer."""

    def test_confirm_escalation_says_no_without_a_terminal(self):
        """The opposite of confirm_action, which proceeds when nobody answers.

        This is the whole point of the second helper: here nobody chose between
        two outcomes, so silence has to select the harmless one.
        """
        assert confirm_escalation("anything?") is False

    def test_a_prompt_nobody_can_answer_is_a_no_not_a_crash(self):
        """Found in the live run of 2026-08-31.

        `isatty()` answered True where nothing could actually reply — under Git
        Bash it even reports True for `< /dev/null` — and `click.confirm` then
        raised Abort and killed the command. Safe in the sense that nothing was
        written, but the caller got "Aborted!" and no recipient at all.

        The guarantee has to be "yes only when a human says yes", not "yes when
        isatty says there is a terminal".
        """
        with patch("contao_ai_cli.cli.helpers.sys.stdin") as fake_stdin, \
             patch("contao_ai_cli.cli.helpers.ask_yes_no", return_value=None):
            fake_stdin.isatty.return_value = True
            assert confirm_escalation("anything?") is False

    def test_creating_without_a_flag_creates_an_inactive_recipient(self):
        b = backend()
        with patch("contao_ai_cli.cli.cli_newsletter._get_backend", return_value=b), \
             patch("contao_ai_cli.cli.cli_newsletter._require_core_bundle"):
            result = CliRunner().invoke(cli, [
                "newsletter", "subscriber-create",
                "--email", "leser@example.com", "--pid", "1",
            ])
        assert result.exit_code == 0, result.output
        assert "--active" not in sent(b)

    def test_the_explicit_flag_still_works_headless(self):
        b = backend()
        with patch("contao_ai_cli.cli.cli_newsletter._get_backend", return_value=b), \
             patch("contao_ai_cli.cli.cli_newsletter._require_core_bundle"):
            result = CliRunner().invoke(cli, [
                "newsletter", "subscriber-create",
                "--email", "leser@example.com", "--pid", "1", "--active",
            ])
        assert result.exit_code == 0, result.output
        assert "--active" in sent(b)

    def test_both_flags_at_once_is_a_usage_error(self):
        with patch("contao_ai_cli.cli.cli_newsletter._require_core_bundle"):
            result = CliRunner().invoke(cli, [
                "newsletter", "subscriber-create",
                "--email", "a@b.c", "--pid", "1", "--active", "--inactive",
            ])
        assert result.exit_code != 0
        assert "not both" in result.output


class TestSendRefusal:
    def test_send_exists_but_fails(self):
        """Registered on purpose. An unregistered command answers "No such
        command", which is indistinguishable from a feature nobody got to yet.
        """
        result = CliRunner().invoke(cli, ["newsletter", "send", "5"])
        assert result.exit_code != 0

    def test_the_refusal_says_it_is_deliberate(self):
        result = CliRunner().invoke(cli, ["newsletter", "send", "5"])
        assert "by design" in result.output

    def test_the_refusal_names_the_workaround_and_rules_it_out(self):
        """The load-bearing sentence. Without it the reader is left to find
        `sent=1` unaided, and that route publishes without sending.
        """
        out = CliRunner().invoke(cli, ["newsletter", "send", "5"]).output
        assert "sent=1" in out
        assert "does not send anything" in out

    def test_the_refusal_points_at_the_back_end(self):
        result = CliRunner().invoke(cli, ["newsletter", "send"])
        assert "back end" in result.output

    def test_the_refusal_text_is_reachable_without_the_cli(self):
        """The bundle's own guard carries the same message; this is the copy an
        agent reading the module sees."""
        assert "by design" in newsletter_mod.newsletter_send_refusal()
