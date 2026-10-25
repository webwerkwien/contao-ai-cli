"""`--json` after any command, and a hint for borrowed command names (v1.15.0).

Until then 26 commands -- most `list` commands among them -- took `--json` only
before the command name. An agent that wrote `news list --json`, the form every
`read` and `update` accepts, got `No such option` and had to guess why.
`content get` failed the same unhelpful way; `get` is what most CLIs call it.
"""
import json

import click
import pytest
from click.testing import CliRunner

from contao_ai_cli import contao_cli
from contao_ai_cli.cli.helpers import COMMAND_SYNONYMS
from contao_ai_cli.contao_cli import cli

# The interactive loop prints nothing a caller would parse.
WITHOUT_JSON = {"repl"}


def leaf_commands(group=cli, path=()):
    for name, cmd in group.commands.items():
        if isinstance(cmd, click.Group):
            yield from leaf_commands(cmd, path + (name,))
        else:
            yield " ".join(path + (name,)), cmd


def takes_json(cmd) -> bool:
    return any("--json" in param.opts for param in cmd.params)


def test_every_command_takes_json_after_its_name():
    leaves = dict(leaf_commands())
    # A walk that found nothing would pass the check below for free.
    assert len(leaves) > 150
    assert {"news list", "content read", "repl"} <= leaves.keys()
    # The known non-match: the scan does tell a command without the flag apart.
    assert not takes_json(leaves["repl"])

    missing = sorted(p for p, c in leaves.items() if p not in WITHOUT_JSON and not takes_json(c))
    assert missing == []


@pytest.mark.parametrize("before", [True, False])
def test_the_flag_after_the_command_reaches_the_shared_context(before):
    # `guide` is one of the commands that read only ctx.obj -- run it both ways.
    args = ["--json", "guide", "--path"] if before else ["guide", "--path", "--json"]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert set(json.loads(result.output)) == {"version", "path"}


def test_without_the_flag_the_answer_stays_text():
    result = CliRunner().invoke(cli, ["guide", "--path"])
    assert result.exit_code == 0
    assert not result.output.startswith("{")


def _main(monkeypatch, capsys, *argv):
    monkeypatch.setattr(contao_cli.sys, "argv", ["contao-ai-cli", *argv])
    with pytest.raises(SystemExit) as exit_info:
        contao_cli.main()
    out, err = capsys.readouterr()
    return exit_info.value.code, out, err


@pytest.mark.parametrize("argv, unknown, hint", [
    (("content", "get", "5"), "get", "Did you mean 'content read'?"),
    (("page", "edit", "5"), "edit", "Did you mean 'page update'?"),
    (("news", "add"), "add", "Did you mean 'news create'?"),
    (("article", "rm", "5"), "rm", "Did you mean 'article delete'?"),
    (("pages", "list"), "pages", "Did you mean 'page'?"),   # a close spelling
])
def test_a_borrowed_name_points_to_ours(monkeypatch, capsys, argv, unknown, hint):
    code, out, err = _main(monkeypatch, capsys, *argv)
    assert code == 2
    assert f"No such command '{unknown}'. {hint}" in err


def test_the_hint_comes_inside_the_json_error(monkeypatch, capsys):
    code, out, err = _main(monkeypatch, capsys, "--json", "content", "get", "5")
    assert code == 2
    assert json.loads(out) == {
        "status": "error", "code": 2,
        "message": "No such command 'get'. Did you mean 'content read'?",
    }


def test_no_hint_where_nothing_fits(monkeypatch, capsys):
    code, out, err = _main(monkeypatch, capsys, "content", "frobnicate")
    assert code == 2
    assert "No such command 'frobnicate'." in err
    assert "Did you mean" not in err


def test_a_synonym_is_offered_only_where_its_target_exists(monkeypatch, capsys):
    # `cache` has no `read`; `cache get` must not point to one.
    assert "cache read" not in dict(leaf_commands())
    code, out, err = _main(monkeypatch, capsys, "cache", "get")
    assert code == 2
    assert "No such command 'get'." in err
    assert "Did you mean" not in err


def test_every_synonym_target_is_a_real_command_somewhere():
    names = {path.split()[-1] for path, _ in leaf_commands()}
    assert set(COMMAND_SYNONYMS.values()) <= names
