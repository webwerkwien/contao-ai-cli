"""REPL: quoted values and declined prompts (v0.30.0).

Until v0.29.0 the REPL split a line with `str.split()`, so `--title "Über uns"`
arrived as two broken arguments, and a declined delete prompt printed a bare red
cross because `str(click.Abort())` is empty.
"""
import click
import pytest
from click.testing import CliRunner

from contao_ai_cli.cli import cli_repl
from contao_ai_cli.cli.cli_repl import split_line


class TestSplitLine:
    def test_quoted_value_with_space_stays_one_argument(self):
        assert split_line('page create --title "Über uns" --pid 1') == [
            "page", "create", "--title", "Über uns", "--pid", "1"]

    def test_single_quotes_and_set_values(self):
        assert split_line("content create --set 'text=<p>Hallo Welt</p>'") == [
            "content", "create", "--set", "text=<p>Hallo Welt</p>"]

    def test_plain_line_as_before(self):
        assert split_line("cache clear") == ["cache", "clear"]

    def test_unclosed_quote_is_an_error(self):
        with pytest.raises(ValueError):
            split_line('page create --title "Über uns')


def run_repl(monkeypatch, lines):
    """Drive the REPL loop with the given input lines against a small fake root CLI."""
    seen, messages = [], []

    @click.group()
    def fake_root():
        pass

    @fake_root.command("echo")
    @click.option("--title")
    def echo(title):
        seen.append(title)

    @fake_root.command("decline")
    def decline():
        raise click.Abort()

    @fake_root.command("usage")
    def usage():
        raise click.UsageError("Nothing to change")

    feed = iter(lines)

    def get_input(session, project_name=None):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError

    import contao_ai_cli.contao_cli as root_module
    monkeypatch.setattr(root_module, "cli", fake_root)
    skin = cli_repl.skin
    monkeypatch.setattr(skin, "get_input", get_input)
    monkeypatch.setattr(skin, "create_prompt_session", lambda: None)
    for name in ("print_banner", "print_goodbye", "info", "help"):
        monkeypatch.setattr(skin, name, lambda *a, **k: None)
    monkeypatch.setattr(skin, "warning", lambda m: messages.append(("warning", m)))
    monkeypatch.setattr(skin, "error", lambda m: messages.append(("error", m)))
    monkeypatch.setattr(cli_repl.session_mod, "load_session", lambda path: None)

    result = CliRunner().invoke(cli_repl.repl, [], obj={"session": None})
    assert result.exit_code == 0, result.output
    return seen, messages


class TestLoop:
    def test_quoted_title_reaches_the_command_whole(self, monkeypatch):
        seen, messages = run_repl(monkeypatch, ['echo --title "Über uns"'])
        assert seen == ["Über uns"]
        assert [m for m in messages if m[0] == "error"] == []

    def test_declined_prompt_is_a_warning_with_text(self, monkeypatch):
        _, messages = run_repl(monkeypatch, ["decline"])
        assert messages[-1] == ("warning", "Aborted, nothing changed.")

    def test_usage_error_keeps_its_message(self, monkeypatch):
        _, messages = run_repl(monkeypatch, ["usage"])
        assert messages[-1] == ("error", "Nothing to change")

    def test_unclosed_quote_is_reported_and_the_loop_goes_on(self, monkeypatch):
        seen, messages = run_repl(monkeypatch, ['echo --title "offen', "echo --title ok"])
        errors = [m for kind, m in messages if kind == "error"]
        assert len(errors) == 1 and "Could not read the line" in errors[0]
        assert seen == ["ok"]
