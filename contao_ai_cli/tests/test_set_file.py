"""
`--set-file FIELD=PATH` — a field value read from a file instead of the command line.

Issue #55. Reported from live work on web.werk.wien: the head HTML of a page could
only be passed as a literal, so the caller's own shell had to carry quotes, `$`,
backticks and newlines intact. The CLI never damaged such a value — `build_set_args`
quotes it and `join_args` carries the comment about not touching it afterwards — but
everything before the CLI did.

Two of these tests exist because of what went wrong with the `--set id=` guard in
core-bundle v1.1.0 on 2026-09-23: nine tests called the guard directly, none checked
that anything called the guard. `test_every_command_with_set_has_set_file` and
`test_the_excluded_commands_are_real_and_still_take_set` are the equivalent here —
they pin the wiring, not the function.
"""
import pathlib
import sys
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

# Importing this module is what attaches the options — see attach_set_file_options.
from contao_ai_cli.contao_cli import SET_FILE_EXCLUDED, attach_set_file_options, cli
from contao_ai_cli.cli import cli_page
from contao_ai_cli.cli.helpers import SET_FILE_META, WINDOWS_ARG_LIMIT, parse_set_fields


def walk(group, prefix=""):
    """Every leaf command in the tree, as (path, command)."""
    ctx = click.Context(group)
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        path = f"{prefix}{name}"
        if isinstance(command, click.Group):
            yield from walk(command, f"{path} ")
        else:
            yield path, command


def opts_of(command):
    return {o for p in command.params for o in getattr(p, "opts", [])}


class TestTheOptionIsWhereItShouldBe:
    def test_every_command_with_set_has_set_file(self):
        """The wiring, not the function. A command added later gets it or this goes red."""
        missing = [path for path, cmd in walk(cli)
                   if "--set" in opts_of(cmd)
                   and "--set-file" not in opts_of(cmd)
                   and path not in SET_FILE_EXCLUDED]
        assert not missing, f"commands with --set but no --set-file: {missing}"

    def test_at_least_one_command_actually_got_it(self):
        """Guards the test above against passing because the tree walk found nothing."""
        got = [path for path, cmd in walk(cli) if "--set-file" in opts_of(cmd)]
        assert len(got) > 20, f"only {len(got)} commands carry --set-file"

    def test_the_excluded_commands_are_real_and_still_take_set(self):
        """An exclusion that names a command that no longer exists is a dead decision."""
        tree = dict(walk(cli))
        for path in SET_FILE_EXCLUDED:
            assert path in tree, f"{path!r} is excluded from --set-file but does not exist"
            assert "--set" in opts_of(tree[path]), f"{path!r} no longer takes --set"
            assert "--set-file" not in opts_of(tree[path])

    def test_a_second_pass_changes_nothing(self):
        """Idempotent: the walk must not stack a second option onto every command.

        On a throwaway group, not on `cli`. Running it against the real tree would
        wire up anything the module-level call had failed to wire, and every test
        after this one would then pass for the wrong reason — measured: with the
        module-level call commented out, only the three tests above went red.
        """
        @click.group()
        def demo():
            pass

        @demo.command("update")
        @click.option("--set", "fields", multiple=True, required=True)
        def demo_update(fields):
            pass

        attach_set_file_options(demo)
        first = len(demo_update.params)
        assert "--set-file" in opts_of(demo_update)
        attach_set_file_options(demo)
        assert len(demo_update.params) == first


class TestReadingTheFile:
    def _fields(self, args, tmp_path):
        """Invoke `page update` and return the dict it would have sent."""
        seen = {}

        def capture(b, command, page_id, ids, ids_from_file, fields):
            seen.update(fields)
            return {"status": "ok"}

        with patch("contao_ai_cli.cli.cli_page._require_core_bundle"), \
             patch("contao_ai_cli.cli.cli_page._get_backend"), \
             patch("contao_ai_cli.cli.cli_page.dispatch_update", side_effect=capture):
            result = CliRunner().invoke(cli_page.page, ["update", "12", *args], obj={})
        return result, seen

    def test_the_file_contents_become_the_value(self, tmp_path):
        head = tmp_path / "head.html"
        head.write_text('<meta name="x" content="a\'b">\n<!-- $notshell `nor this` -->\n',
                        encoding="utf-8")
        result, fields = self._fields(["--set-file", f"head={head}"], tmp_path)
        assert result.exit_code == 0, result.output
        # read_bytes, not read_text: read_text would translate the line endings on
        # the way back in and the comparison would agree with itself, not with the file.
        assert fields == {"head": head.read_bytes().decode("utf-8")}

    def test_newlines_and_quotes_survive_unchanged(self, tmp_path):
        """Nothing trims, nothing translates line endings — a textarea submits CRLF too."""
        raw = "line 1\r\nline 2 with 'single' and \"double\"\n\n"
        f = tmp_path / "v.txt"
        f.write_bytes(raw.encode("utf-8"))
        _, fields = self._fields(["--set-file", f"cssID={f}"], tmp_path)
        assert fields["cssID"] == raw

    def test_it_mixes_with_plain_set(self, tmp_path):
        f = tmp_path / "v.txt"
        f.write_text("BODY", encoding="utf-8")
        _, fields = self._fields(["--set", "title=Home", "--set-file", f"head={f}"], tmp_path)
        assert fields == {"title": "Home", "head": "BODY"}

    def test_the_same_field_twice_is_refused(self, tmp_path):
        f = tmp_path / "v.txt"
        f.write_text("BODY", encoding="utf-8")
        result, fields = self._fields(["--set", "head=A", "--set-file", f"head={f}"], tmp_path)
        assert result.exit_code != 0
        assert "both --set and --set-file" in result.output
        assert fields == {}

    def test_a_missing_file_writes_nothing(self, tmp_path):
        result, fields = self._fields(["--set-file", f"head={tmp_path / 'gone.html'}"], tmp_path)
        assert result.exit_code != 0
        assert "cannot read" in result.output
        assert fields == {}

    def test_a_file_that_is_not_utf8_writes_nothing(self, tmp_path):
        f = tmp_path / "cp1252.html"
        f.write_bytes("Gr\xfc\xdfe".encode("cp1252"))
        result, fields = self._fields(["--set-file", f"head={f}"], tmp_path)
        assert result.exit_code != 0
        assert "not UTF-8" in result.output
        assert fields == {}

    @pytest.mark.parametrize("spec", ["head", "=path.html", "head="])
    def test_a_malformed_spec_is_refused(self, spec, tmp_path):
        result, fields = self._fields(["--set-file", spec], tmp_path)
        assert result.exit_code != 0
        assert fields == {}

    def test_the_same_field_given_twice_by_file_is_refused(self, tmp_path):
        a, b = tmp_path / "a.txt", tmp_path / "b.txt"
        a.write_text("A", encoding="utf-8")
        b.write_text("B", encoding="utf-8")
        result, fields = self._fields(
            ["--set-file", f"head={a}", "--set-file", f"head={b}"], tmp_path)
        assert result.exit_code != 0
        assert "given twice" in result.output
        assert fields == {}

    @pytest.mark.skipif(sys.platform != "win32", reason="the argv cap this guards is a Windows one")
    def test_a_value_too_long_for_the_windows_command_line_is_refused(self, tmp_path):
        f = tmp_path / "big.html"
        f.write_text("x" * (WINDOWS_ARG_LIMIT + 10), encoding="utf-8")
        result, fields = self._fields(["--set-file", f"head={f}"], tmp_path)
        assert result.exit_code != 0
        assert "too large" in result.output and "Nothing was written" in result.output
        assert fields == {}


class TestNothingToChange:
    def test_update_without_either_option_never_reaches_the_server(self):
        """`--set` lost `required`; the refusal must still come before _get_backend."""
        with patch("contao_ai_cli.cli.cli_page._get_backend") as backend:
            result = CliRunner().invoke(cli_page.page, ["update", "12"], obj={})
        assert result.exit_code != 0
        assert "--set" in result.output and "--set-file" in result.output
        backend.assert_not_called()

    def test_set_file_alone_is_enough(self, tmp_path):
        """The whole point: a long value needs no companion --set."""
        f = tmp_path / "v.txt"
        f.write_text("BODY", encoding="utf-8")
        with patch("contao_ai_cli.cli.cli_page._require_core_bundle"), \
             patch("contao_ai_cli.cli.cli_page._get_backend"), \
             patch("contao_ai_cli.cli.cli_page.dispatch_update", return_value={"status": "ok"}):
            result = CliRunner().invoke(
                cli_page.page, ["update", "12", "--set-file", f"head={f}"], obj={})
        assert result.exit_code == 0, result.output


class TestTheMetaSlotDoesNotLeak:
    def test_parse_set_fields_takes_the_values_rather_than_copying_them(self, tmp_path):
        """The REPL reuses one context; a value left behind lands in the next record."""
        f = tmp_path / "v.txt"
        f.write_text("BODY", encoding="utf-8")

        @click.command()
        @click.option("--set", "fields", multiple=True)
        @click.pass_context
        def demo(ctx, fields):
            first = parse_set_fields(fields)
            second = parse_set_fields(())
            click.echo(f"{first}|{second}")

        demo.params.append(__import__("contao_ai_cli.cli.helpers", fromlist=["x"]).set_file_option())
        result = CliRunner().invoke(demo, ["--set-file", f"head={f}"])
        assert result.output.strip() == "{'head': 'BODY'}|{}"

    def test_an_invocation_without_the_option_clears_the_slot(self, tmp_path):
        """Not merely "does not add" — it must overwrite what a previous command left."""
        ctx = click.Context(click.Command("demo"))
        ctx.meta[SET_FILE_META] = {"stale": "from the last command"}
        with ctx:
            from contao_ai_cli.cli.helpers import set_file_callback
            set_file_callback(ctx, None, ())
            assert parse_set_fields(["title=Home"]) == {"title": "Home"}


def test_parse_set_fields_still_works_without_a_click_context():
    """Called directly in tests and conceivably as a library; no context is not an error."""
    assert parse_set_fields(["a=b"]) == {"a": "b"}
