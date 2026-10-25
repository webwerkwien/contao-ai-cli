"""`apply --file` hands a plan to contao:ai:apply in one connection (v1.16.0).

The server checks the plan and runs it all or nothing; the CLI reads the file,
asks once for deletions, picks a time limit and reports what came back.
"""
import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli import cli_apply
from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import apply as apply_mod

PLAN = {"steps": [
    {"ref": "a", "do": "page create", "title": "A", "pid": 1},
    {"do": "content delete", "id": 5},
]}


def backend(stdout, returncode=0):
    b = MagicMock()
    b.run.return_value = {"stdout": stdout, "stderr": "", "returncode": returncode}
    b.undefined_command_hint.return_value = ""
    return b


def test_the_plan_goes_over_stdin_in_one_call():
    b = backend('{"status": "ok", "count": 2, "refs": {"a": 7}, "steps": []}')
    text = json.dumps(PLAN)

    answer = apply_mod.run_apply(b, text, dry_run=False, steps=2)

    assert answer["refs"] == {"a": 7}
    b.run.assert_called_once()
    cmd = b.run.call_args.args[0]
    assert cmd.startswith("contao:ai:apply")
    assert "--dry-run" not in cmd
    assert b.run.call_args.kwargs["stdin_data"] == text
    assert b.run.call_args.kwargs["check"] is False


def test_dry_run_and_time_limit():
    b = backend('{"status": "ok", "dryRun": true}')
    apply_mod.run_apply(b, "{}", dry_run=True, steps=300)

    assert "--dry-run" in b.run.call_args.args[0]
    assert b.run.call_args.kwargs["timeout"] == 600   # 60 + 2 * 300, capped
    apply_mod.run_apply(b, "{}", dry_run=True, steps=10)
    assert b.run.call_args.kwargs["timeout"] == 80


def test_a_refused_plan_keeps_its_answer():
    payload = {"status": "error", "message": "The plan was refused", "problems": ["Step 0: …"]}
    b = backend(json.dumps(payload), returncode=1)

    with pytest.raises(apply_mod.ApplyFailed) as info:
        apply_mod.run_apply(b, "{}", dry_run=False, steps=1)

    assert info.value.payload == payload


def test_an_error_answer_with_exit_code_zero_is_a_failure():
    payload = {"status": "error", "message": "refused"}
    b = backend(json.dumps(payload), returncode=0)

    with pytest.raises(apply_mod.ApplyFailed):
        apply_mod.run_apply(b, "{}", dry_run=False, steps=1)


def test_the_command_hands_on_dry_run_and_the_step_count(tmp_path, monkeypatch):
    f = tmp_path / "plan.json"
    f.write_text(json.dumps({"steps": [PLAN["steps"][0]] * 10}), encoding="utf-8")
    b = backend('{"status": "ok", "dryRun": true, "count": 10, "steps": []}')
    monkeypatch.setattr(cli_apply, "_get_backend", lambda s=None: b)

    result = CliRunner().invoke(cli, ["apply", "--file", str(f), "--dry-run", "--json"])

    assert result.exit_code == 0, result.output
    assert "--dry-run" in b.run.call_args.args[0]
    assert b.run.call_args.kwargs["timeout"] == 80   # 60 + 2 * 10

    CliRunner().invoke(cli, ["apply", "--file", str(f), "--json"])
    assert "--dry-run" not in b.run.call_args.args[0]


def test_a_timeout_says_the_run_may_have_written():
    b = MagicMock()
    b.run.side_effect = apply_mod.ContaoBackendError("SSH command timed out after 80s")

    with pytest.raises(apply_mod.ContaoBackendError) as info:
        apply_mod.run_apply(b, "{}", dry_run=False, steps=10)

    assert "may still have written" in str(info.value)


def test_no_json_back_names_what_the_server_said():
    b = backend("", returncode=1)
    b.run.return_value["stderr"] = 'Command "contao:ai:apply" is not defined.'
    b.undefined_command_hint.return_value = "\nneeds core-bundle v1.13.0"

    with pytest.raises(apply_mod.ContaoBackendError) as info:
        apply_mod.run_apply(b, "{}", dry_run=False, steps=1)

    assert "is not defined" in str(info.value)
    assert "v1.13.0" in str(info.value)


def test_the_file_must_be_json(tmp_path):
    f = tmp_path / "plan.json"
    f.write_text("{steps: [", encoding="utf-8")

    result = CliRunner().invoke(cli, ["apply", "--file", str(f)])

    assert result.exit_code == 2
    assert "not valid JSON" in result.output


def test_a_bom_is_not_part_of_the_plan(tmp_path, monkeypatch):
    f = tmp_path / "plan.json"
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps({"steps": [PLAN["steps"][0]]}).encode())
    b = backend('{"status": "ok", "count": 1, "steps": []}')
    monkeypatch.setattr(cli_apply, "_get_backend", lambda s=None: b)

    result = CliRunner().invoke(cli, ["apply", "--file", str(f), "--json"])

    assert result.exit_code == 0, result.output
    assert not b.run.call_args.kwargs["stdin_data"].startswith("﻿")


def test_deletions_are_named_once(tmp_path, monkeypatch):
    f = tmp_path / "plan.json"
    f.write_text(json.dumps(PLAN), encoding="utf-8")
    asked = []
    monkeypatch.setattr(cli_apply, "confirm_action", lambda q, y: asked.append(q) or True)
    monkeypatch.setattr(cli_apply, "_get_backend", lambda s=None: backend('{"status": "ok", "count": 2, "steps": []}'))

    result = CliRunner().invoke(cli, ["apply", "--file", str(f), "--json"])

    assert result.exit_code == 0, result.output
    assert asked == ["Run a plan with 1 deletion(s)?"]


def test_a_failure_under_json_is_the_servers_answer(tmp_path, monkeypatch):
    f = tmp_path / "plan.json"
    f.write_text(json.dumps({"steps": [PLAN["steps"][0]]}), encoding="utf-8")
    payload = {"status": "error", "code": 1, "rolledBack": True,
               "failedStep": {"index": 0, "do": "page create", "message": "Title is required"}}
    monkeypatch.setattr(cli_apply, "_get_backend", lambda s=None: backend(json.dumps(payload), returncode=1))

    result = CliRunner().invoke(cli, ["apply", "--file", str(f), "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output) == payload


def test_a_refused_plan_lists_every_problem(tmp_path, monkeypatch):
    f = tmp_path / "plan.json"
    f.write_text(json.dumps({"steps": [{"do": "page get"}]}), encoding="utf-8")
    payload = {"status": "error", "message": "The plan was refused before anything was written.",
               "problems": ["Step 0: unknown \"do\"", "Step 1: \"id\" is required."]}
    monkeypatch.setattr(cli_apply, "_get_backend", lambda s=None: backend(json.dumps(payload), returncode=1))

    result = CliRunner().invoke(cli, ["apply", "--file", str(f)])

    assert result.exit_code == 1
    assert "Step 0" in result.output and "Step 1" in result.output
