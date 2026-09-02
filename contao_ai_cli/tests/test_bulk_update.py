"""
`--ids` / `--ids-from-file` — the deterministic bulk path.

Setting one field on 174 pages cost about four minutes on 2026-08-29: 1.4 s per
record, 0.67 s of which was establishing the SSH connection and nothing else.
The only alternative on offer was `bridge rewrite`, an LLM loop that bills API
tokens to write a constant. This closes the gap.

One connection, one console invocation — but still one version per record on
the server, because the audit trail is the reason writes go through the console
at all.
"""
import io
import json
from unittest.mock import MagicMock, patch

import click
import pytest

from contao_ai_cli.cli.helpers import resolve_bulk_ids
from contao_ai_cli.core.contao_ops import run_bulk_update, BulkUpdateFailed
from contao_ai_cli.utils.contao_backend import ContaoBackendError


class TestResolveBulkIds:
    def test_a_single_id_stays_a_single_id(self):
        assert resolve_bulk_ids(39, None, None) == [39]

    def test_reads_a_comma_separated_list(self):
        assert resolve_bulk_ids(None, "39,40,41", None) == [39, 40, 41]

    def test_tolerates_spacing_in_the_list(self):
        assert resolve_bulk_ids(None, " 39 , 40,41 ", None) == [39, 40, 41]

    def test_reads_a_file_one_id_per_line(self, tmp_path):
        f = tmp_path / "ids.txt"
        f.write_text("39\n40\n\n41\n", encoding="utf-8")

        assert resolve_bulk_ids(None, None, str(f)) == [39, 40, 41]

    def test_ignores_comments_in_a_file(self, tmp_path):
        f = tmp_path / "ids.txt"
        f.write_text("# tour pages, de\n39\n40  # keep\n", encoding="utf-8")

        assert resolve_bulk_ids(None, None, str(f)) == [39, 40]

    def test_drops_duplicates_but_keeps_order(self):
        assert resolve_bulk_ids(None, "41,39,41,40", None) == [41, 39, 40]

    def test_refuses_when_nothing_was_given(self):
        with pytest.raises(ValueError, match="--ids"):
            resolve_bulk_ids(None, None, None)

    @pytest.mark.parametrize("args", [
        (39, "40,41", None),
        (39, None, "ids.txt"),
        (None, "40,41", "ids.txt"),
    ])
    def test_refuses_more_than_one_source(self, args):
        with pytest.raises(ValueError):
            resolve_bulk_ids(*args)

    def test_names_a_malformed_entry_instead_of_skipping_it(self):
        """A silent skip is exactly how the 2026-08-29 run looked successful."""
        with pytest.raises(ValueError, match="foo"):
            resolve_bulk_ids(None, "39,foo,41", None)

    def test_refuses_an_empty_file(self, tmp_path):
        f = tmp_path / "ids.txt"
        f.write_text("\n\n", encoding="utf-8")

        with pytest.raises(ValueError):
            resolve_bulk_ids(None, None, str(f))

    def test_reports_a_missing_file_by_name(self, tmp_path):
        with pytest.raises(ValueError, match="nope.txt"):
            resolve_bulk_ids(None, None, str(tmp_path / "nope.txt"))


class TestRunBulkUpdate:
    def test_sends_one_command_with_all_ids(self):
        backend = MagicMock()
        backend.run.return_value = {"returncode": 0, "stdout": "{}", "stderr": ""}

        run_bulk_update(backend, "contao:page:update", [39, 40, 41], {"max_teiln": "4"})

        sent = backend.run.call_args[0][0]
        assert "--ids=39,40,41" in sent
        assert "max_teiln=4" in sent
        assert " 39 " not in sent, "The ID must not also be passed as an argument."

    def test_one_invocation_not_one_per_record(self):
        backend = MagicMock()
        backend.run.return_value = {"returncode": 0, "stdout": "{}", "stderr": ""}

        run_bulk_update(backend, "contao:page:update", list(range(1, 51)), {"x": "y"})

        assert backend.run.call_count == 1, "The point of the exercise is one connection."

    def test_a_partial_run_raises_but_keeps_its_summary(self):
        """
        Both halves matter, and this test used to hold only one of them.

        The original concern was right: `ContaoBackend.run()` raises on a
        non-zero exit, and that threw away the very payload naming the failures
        (found on c5, 2026-08-29). The answer then was `check=False` and
        returning the summary.

        🔴 Audit 2026-09-02 (M-3) found what that traded away. Returning
        normally meant `contao-ai-cli … --ids=…` exited **0** after "1 of 2
        records failed". An agent reading the JSON saw `failed`; a shell script
        checking `$?` saw success. Same answer, two meanings.

        ⚠️ The test as written asserted exactly that — `result == summary`, no
        error — so it certified the defect. It is the fourth of its kind found
        this day. Inverted rather than deleted: the requirement it was protecting
        is real, it just was not the whole requirement.

        Now: raise (so `$?` is right) **and** carry the summary (so the caller
        keeps what it needs). `show()` puts it on stdout.
        """
        summary = {
            "status": "partial", "total": 2, "succeeded": 1, "failed": 1,
            "ids": [105], "errors": [{"id": 999999, "message": "Page not found: 999999"}],
        }
        backend = MagicMock()
        backend.run.return_value = {
            "returncode": 1, "stdout": json.dumps(summary), "stderr": "",
        }

        with pytest.raises(BulkUpdateFailed) as excinfo:
            run_bulk_update(backend, "contao:page:update", [105, 999999], {"x": "y"})

        # The payload survives — that was the point of the original fix.
        assert excinfo.value.summary == summary
        assert excinfo.value.returncode == 1
        assert "1 of 2" in str(excinfo.value)
        assert backend.run.call_args.kwargs.get("check") is False

    def test_the_summary_reaches_stdout_when_the_error_is_shown(self):
        """A caller that only reads stdout must still get the failed record ids."""
        summary = {"status": "partial", "total": 2, "failed": 1,
                   "errors": [{"id": 999999, "message": "Page not found: 999999"}]}
        buf = io.StringIO()

        with patch("sys.stdout", buf), patch.object(click.ClickException, "show", lambda self, file=None: None):
            BulkUpdateFailed(summary, 1).show()

        assert json.loads(buf.getvalue()) == summary

    def test_a_genuine_failure_still_raises(self):
        """No JSON back means the command did not run — that is not a partial result."""
        backend = MagicMock()
        backend.run.return_value = {
            "returncode": 255, "stdout": "", "stderr": "Could not open input file",
        }

        with pytest.raises(ContaoBackendError):
            run_bulk_update(backend, "contao:page:update", [1], {"x": "y"})
