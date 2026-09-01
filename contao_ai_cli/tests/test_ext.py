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

    def test_infrastructure_is_not_counted_as_wrapped(self):
        """Third recurrence of the same shape in one day.

        The infrastructure list names its commands as string literals in
        core/ext.py, so the AST scan finds them there — naming a command in
        order to set it aside would have marked it as handled. Before this,
        `ext list` reported 136 wrapped, 0 infrastructure and 0 available: the
        exclusion had erased itself.

        The first was `ext run`'s help-text example, the second a docstring.
        """
        wrapped = ext_mod.wrapped_commands()
        for name in ext_mod._INFRASTRUCTURE:
            assert name not in wrapped, f"{name} counts as wrapped because it is named"

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

    def test_infrastructure_is_set_aside_but_counted(self):
        """Set aside, not hidden. A silent filter would make `ext list` quietly
        incomplete — the failure this whole group exists to fix."""
        listing = json.dumps({
            "status": "ok", "count": 2,
            "commands": [
                {"name": "contao:supervise-workers", "description": "plumbing"},
                {"name": "contao:some-plugin:sync", "description": "real"},
            ],
        })

        default = ext_mod.ext_list(backend(listing))
        assert default["infrastructure"] == 1
        assert default["available"] == 1
        assert [c["name"] for c in default["commands"]] == ["contao:some-plugin:sync"]

        shown = ext_mod.ext_list(backend(listing), include_infrastructure=True)
        assert shown["available"] == 2
        assert any(c.get("infrastructure") for c in shown["commands"]),             "--all must say WHY each one is normally set aside"

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

    def test_a_command_outside_contao_is_refused_before_the_warning(self):
        """The warning ends with "the invocation is recorded in the system log".
        For a command the server refuses, nothing is recorded — printing it
        first stated something about a run that was not going to happen."""
        b = backend('{"status":"ok"}')
        result = self._run(["run", "doctrine:query:sql", "SELECT 1"], b)

        assert result.exit_code != 0
        assert "system log" not in result.output
        assert "outside the contao: namespace" in result.output
        b.run.assert_not_called()

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


class TestExtRunEnvelope:
    """
    A foreign command's answer is reported as foreign, not as the CLI's own.

    Measured on c5-axeltest on 2026-09-01 with a throwaway plugin. `ext run`
    returned the plugin's stdout verbatim:

        { "status": "ok", "echo": "HALLO" }

    That `status: ok` is the plugin's word, printed where every wrapped command
    prints the CLI's. For a wrapped command the CLI knows the shape, because the
    core bundle produces it. For an unwrapped one the shape is unknown by
    definition — a plugin can answer `status: ok` and have done nothing, or exit
    non-zero while its JSON still says ok.

    The server deliberately does not normalise it ("its shape is its own",
    AiRunCommand), so the envelope belongs here.
    """

    @staticmethod
    def _backend(stdout, returncode=0, stderr=""):
        b = MagicMock()
        b.run.return_value = {"stdout": stdout, "returncode": returncode, "stderr": stderr}
        # Explicit: a bare MagicMock would answer with another MagicMock, which
        # then lands in the envelope and is not JSON-serialisable. The real
        # method returns a string or "".
        b.undefined_command_hint.return_value = ""
        return b

    def test_the_plugin_answer_sits_under_output(self):
        b = self._backend('{"status":"ok","echo":"HALLO"}')
        result = ext_mod.ext_run(b, "contao:demo:ping hallo")

        assert result["command_output"] == {"status": "ok", "echo": "HALLO"}
        assert "echo" not in result

    def test_a_plugin_claiming_ok_while_failing_does_not_set_the_status(self):
        """The case the envelope exists for."""
        b = self._backend('{"status":"ok"}', returncode=1)
        result = ext_mod.ext_run(b, "contao:demo:ping")

        assert result["status"] == "error"
        assert result["exit_code"] == 1
        assert result["command_output"] == {"status": "ok"}

    def test_it_names_the_command_and_says_it_is_unwrapped(self):
        b = self._backend('{"status":"ok"}')
        result = ext_mod.ext_run(b, "contao:demo:ping hallo --upper")

        assert result["command"] == "contao:demo:ping hallo --upper"
        assert result["wrapped"] is False

    def test_non_json_output_survives_as_a_string(self):
        b = self._backend("pong")
        result = ext_mod.ext_run(b, "contao:demo:ping")

        assert result["command_output"] == "pong"
        assert result["status"] == "ok"

    def test_stderr_is_carried_when_there_is_any(self):
        b = self._backend("", returncode=1, stderr="RuntimeException: nope")
        result = ext_mod.ext_run(b, "contao:demo:ping --gibtsnicht")

        assert "nope" in result["stderr"]

    def test_the_envelope_survives_human_mode(self):
        """
        `_output()` prints a field named `output` *instead of* the dict around
        it — a convention about 40 commands use for raw stdout. The envelope's
        payload is deliberately not called that: under the old name the whole
        envelope disappeared in the one mode a person reads, taking `wrapped`
        and `exit_code` with it.
        """
        b = self._backend('{"status":"ok","echo":"HALLO"}')
        with patch("contao_ai_cli.cli.cli_ext._get_backend", return_value=b),              patch("contao_ai_cli.cli.cli_ext._require_core_bundle"):
            result = CliRunner().invoke(cli, ["ext", "run", "contao:demo:ping"])

        assert '"wrapped": false' in result.output
        assert '"exit_code": 0' in result.output

    def test_no_stderr_key_when_there_was_none(self):
        b = self._backend('{"status":"ok"}')
        assert "stderr" not in ext_mod.ext_run(b, "contao:demo:ping")

    def test_stderr_is_dropped_on_a_successful_run(self):
        """
        c5 emits ionCube and imagick startup warnings on every PHP call. Carried
        unconditionally, several lines of unrelated noise would precede every
        successful run and train a reader to skip the field entirely.

        The absence of `stderr` therefore means "the run succeeded", not
        "stderr was empty" — stated in the code, not left to be inferred.
        """
        b = self._backend('{"status":"ok"}', returncode=0, stderr="Cannot load the ionCube PHP Loader")
        assert "stderr" not in ext_mod.ext_run(b, "contao:demo:ping")

    def test_the_process_exits_non_zero_when_the_foreign_command_failed(self):
        """
        Otherwise a script wrapping `ext run` reads success from a failed run.
        The envelope reports the exit code; the process has to carry it too.
        """
        b = self._backend('{"status":"ok"}', returncode=1)
        with patch("contao_ai_cli.cli.cli_ext._get_backend", return_value=b), \
             patch("contao_ai_cli.cli.cli_ext._require_core_bundle"):
            result = CliRunner().invoke(cli, ["ext", "run", "contao:demo:ping"])

        assert result.exit_code != 0
        # and the envelope was still printed, not swallowed by the failure
        assert "exit_code" in result.output


class TestExtRunVersionHint:
    """
    ext run reads the exit code itself, so the hint had to be added here.

    The version hint rides on `backend.run()` raising. `ext_run` passes
    `check=False` — deliberately, so a failing foreign command still reports
    its own output — and therefore never saw it. Measured by the ww-buchung
    session on 2026-09-01: `ext run` and `ext describe` are precisely what a
    caller reaches for when asking about a command it does not have, and both
    were silent about the version.
    """

    @staticmethod
    def _backend(stdout, returncode=1, hint="the hint"):
        b = MagicMock()
        b.run.return_value = {"stdout": stdout, "returncode": returncode, "stderr": ""}
        b.undefined_command_hint.return_value = hint
        return b

    def test_a_failing_run_carries_the_hint(self):
        b = self._backend('{"status":"error","message":"Command not found: contao:x:y"}')
        result = ext_mod.ext_run(b, "contao:x:y")

        assert result["hint"] == "the hint"

    def test_both_streams_are_offered_to_the_recogniser(self):
        """The core bundle answers on stdout, Symfony on stderr."""
        b = self._backend('{"message":"Command not found: contao:x:y"}')
        ext_mod.ext_run(b, "contao:x:y")

        assert b.undefined_command_hint.called
        assert "Command not found" in b.undefined_command_hint.call_args[0][0]

    def test_no_hint_key_when_there_is_nothing_to_say(self):
        b = self._backend('{"status":"error"}', hint="")
        assert "hint" not in ext_mod.ext_run(b, "contao:x:y")

    def test_a_successful_run_is_not_asked_about_versions(self):
        """No extra round trip on the path that worked."""
        b = self._backend('{"status":"ok"}', returncode=0)
        result = ext_mod.ext_run(b, "contao:x:y")

        assert "hint" not in result
        assert not b.undefined_command_hint.called


class TestExtRunWarningWithAContract:
    """
    The blanket warning became untrue the moment contracts existed.

    It ends with "no promise that it writes a version, an undo entry or a log
    line of its own" — correct for a silent plugin, and wrong for one that has
    declared `trace: ['tl_log'], traceWhen: 'before'`. Saying "nothing is
    promised" where something was is the same failure as every other one this
    week: a sentence that is easy to read and no longer matches the thing it
    describes.

    🎯 What the replacement must not do is overcorrect. A declaration is the
    command's own word; this CLI cannot enforce any of it. The warning says
    what was declared **and** that nobody checked it — dropping either half
    would mislead in one direction or the other.
    """

    CONTRACT = {
        "checked": {"tables": ["tl_news"], "tables_with_dca": ["tl_news"]},
        "checked_with_statement": {
            "writes": True,
            "trace": ["tl_log"],
            "trace_when": "before",
            "retention": {"tl_log": {"setting": "logPeriod", "seconds": 604800, "days": 7}},
        },
        "declared": {
            "irreversible_outside_database": "sends a confirmation mail to the guest",
            "repeatable": False,
        },
    }

    def test_a_declared_trail_is_named_instead_of_denied(self):
        lines = ext_mod.contract_warning(self.CONTRACT)

        assert "tl_log" in lines
        assert "before" in lines

    def test_the_retention_travels_with_the_trail(self):
        """"Writes a log entry" and "writes a version" are an order of
        magnitude apart in how long they survive."""
        assert "7" in ext_mod.contract_warning(self.CONTRACT)

    def test_the_irreversible_effect_is_the_prominent_line(self):
        lines = ext_mod.contract_warning(self.CONTRACT)

        assert "confirmation mail" in lines
        assert "cannot be undone" in lines.lower()

    def test_it_says_nobody_checked_any_of_it(self):
        lines = ext_mod.contract_warning(self.CONTRACT)

        assert "declar" in lines.lower()
        assert "cannot" in lines.lower()

    def test_no_contract_means_no_replacement(self):
        assert ext_mod.contract_warning(None) == ""
        assert ext_mod.contract_warning({}) == ""

    def test_a_contract_with_only_problems_is_not_dressed_up_as_one(self):
        """A declaration that failed validation promises nothing."""
        assert ext_mod.contract_warning({"problems": ["trace must be a list"]}) == ""


class TestTheWarningDoesNotContradictItself:
    """
    The first version appended the contract to the blanket warning.

    The result said "no promise that it writes a version, an undo entry or a
    log line of its own" and then, two lines later, "trail tl_log kept 7 days,
    written before the run". One message making both claims — caught by reading
    the live output rather than by a test, which is why this one exists now.
    """

    def _warn(self, contract):
        b = MagicMock()
        b.run.return_value = {"stdout": json.dumps({"status": "ok"}), "returncode": 0, "stderr": ""}
        b.undefined_command_hint.return_value = ""
        with patch("contao_ai_cli.cli.cli_ext._get_backend", return_value=b), \
             patch("contao_ai_cli.cli.cli_ext._require_core_bundle"), \
             patch("contao_ai_cli.core.ext.ext_describe", return_value={"contract": contract}):
            return CliRunner().invoke(cli, ["ext", "run", "contao:demo:ping"]).output

    def test_the_no_promise_sentence_is_dropped_when_a_trail_is_declared(self):
        out = self._warn(TestExtRunWarningWithAContract.CONTRACT)

        assert "no promise that it writes" not in out
        assert "tl_log" in out

    def test_the_guarantees_that_still_do_not_apply_are_still_named(self):
        """Dropping the whole warning would overcorrect: a declaration is not
        a wrapper, and field conversion and the DCA check are still absent."""
        out = self._warn(TestExtRunWarningWithAContract.CONTRACT)

        assert "no field conversion" in out
        assert "DCA check" in out

    def test_without_a_contract_the_blanket_warning_is_unchanged(self):
        out = self._warn(None)

        assert "no promise that it writes" in out
