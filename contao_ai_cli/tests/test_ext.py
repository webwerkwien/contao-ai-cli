"""
The ext group: what this installation offers that the CLI does not wrap.

An extension registers its own contao:* console command with Symfony and is
then invisible from here — it exists on the server, and nothing in the CLI, or
in an agent reading --help, can learn that it does.

Two halves are pinned here, and they were one decision (2026-09-01): the caller
gets a warning before the effect, and the server records the invocation for
whoever asks afterwards. Either alone leaves one of the two without an answer.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import ext as ext_mod


def backend(payload):
    b = MagicMock()
    b.run.return_value = {"stdout": payload, "returncode": 0, "stderr": ""}
    return b


def sent(b) -> str:
    return b.run.call_args[0][0]


LISTING = json.dumps({
    "status": "ok",
    "count": 3,
    "commands": [
        {"name": "contao:page:tree", "description": "wrapped"},
        {"name": "contao:some-plugin:sync", "description": "not wrapped"},
        {"name": "contao:another:thing", "description": "not wrapped either"},
    ],
})


class TestWrappedCommands:
    """The set is derived from the source, not maintained by hand."""

    def test_the_scan_finds_the_commands_the_cli_uses(self):
        """A scan that finds nothing passes as quietly as one that finds
        everything — the lesson this project keeps re-learning. Without the
        count, an empty set would make every command look unwrapped and `ext
        list` would offer the whole console as if it were undiscovered."""
        wrapped = ext_mod.wrapped_commands()
        assert len(wrapped) > 100, f"only {len(wrapped)} found — the scan has drifted"
        assert "contao:page:tree" in wrapped
        assert "contao:record:list" in wrapped

    def test_its_own_two_commands_count_as_wrapped(self):
        """`ext list` and `ext run` are their wrappers. Leaving them out made
        them appear as things the CLI cannot reach — through the very command
        that reaches them."""
        wrapped = ext_mod.wrapped_commands()
        assert "contao:ai:commands" in wrapped
        assert "contao:ai:run" in wrapped


class TestExtList:
    def test_it_asks_the_server_and_subtracts_here(self):
        b = backend(LISTING)
        result = ext_mod.ext_list(b)

        assert sent(b) == "contao:ai:commands"
        assert result["available"] == 2
        assert [c["name"] for c in result["commands"]] == [
            "contao:some-plugin:sync", "contao:another:thing",
        ]

    def test_a_wrapped_command_is_not_offered(self):
        result = ext_mod.ext_list(backend(LISTING))
        assert "contao:page:tree" not in [c["name"] for c in result["commands"]]


class TestRefuseWrapped:
    """Not a safety rule — the wrapped command would run fine. It is about
    there being one answer to "how do I do X"."""

    def test_a_wrapped_command_is_refused(self):
        message = ext_mod.refuse_wrapped("contao:page:read 2")
        assert message is not None
        assert "contao:page:read" in message

    def test_an_unwrapped_command_passes(self):
        assert ext_mod.refuse_wrapped("contao:some-plugin:sync --dry-run") is None

    def test_the_refusal_says_why_rather_than_just_no(self):
        message = ext_mod.refuse_wrapped("contao:page:read 2") or ""
        assert "DCA" in message


class TestExtRun:
    def test_it_goes_through_the_server_command(self):
        b = backend('{"status":"ok"}')
        ext_mod.ext_run(b, "contao:some-plugin:sync --dry-run")
        cmd = sent(b)
        assert cmd.startswith("contao:ai:run --command-line=")
        assert "contao:some-plugin:sync --dry-run" in cmd

    def test_the_operator_travels_when_given(self):
        b = backend('{"status":"ok"}')
        ext_mod.ext_run(b, "contao:x:y", operator="michael")
        assert "--operator=michael" in sent(b)


class TestExtRunCommand:
    def _run(self, args, b):
        with patch("contao_ai_cli.cli.cli_ext._get_backend", return_value=b), \
             patch("contao_ai_cli.cli.cli_ext._require_core_bundle"):
            return CliRunner().invoke(cli, ["ext", *args])

    def test_a_wrapped_command_is_refused_before_anything_is_sent(self):
        b = backend('{"status":"ok"}')
        result = self._run(["run", "contao:page:read", "2"], b)

        assert result.exit_code != 0
        b.run.assert_not_called()

    def test_an_unwrapped_command_runs_and_warns(self):
        """The warning is half the decision; the server's log entry is the
        other half. This pins the half that reaches the caller."""
        b = backend('{"status":"ok"}')
        result = self._run(["run", "contao:some-plugin:sync"], b)

        assert result.exit_code == 0
        assert "not wrapped by this CLI" in result.output
        assert "system log" in result.output

    def test_the_warning_names_what_is_not_guaranteed(self):
        """"Be careful" would be noise. What a caller can act on is which
        specific guarantees do not apply."""
        b = backend('{"status":"ok"}')
        out = self._run(["run", "contao:some-plugin:sync"], b).output

        assert "DCA check" in out
        assert "version" in out
