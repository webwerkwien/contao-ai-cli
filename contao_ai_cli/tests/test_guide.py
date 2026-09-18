"""`contao-ai-cli guide` hands out the agent guide of the installed version (v0.26.0).

Until then the guide existed only in the repository, and an agent working in a
Contao project with a pipx install never saw it.
"""
import json
import pathlib

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli import cli_guide
from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import update_notice

REPO = pathlib.Path(__file__).resolve().parent.parent.parent


def run(*args):
    return CliRunner().invoke(cli, list(args))


def test_prints_the_guide_of_this_checkout():
    result = run("guide")
    assert result.exit_code == 0, result.output
    assert result.output == (REPO / "AGENTS.md").read_text(encoding="utf-8")


def test_path_prints_only_the_location():
    # In a checkout nothing sits inside the package, so the repo root must be found.
    result = run("guide", "--path")
    assert result.exit_code == 0
    assert pathlib.Path(result.output.strip()) == REPO / "AGENTS.md"


def test_json_carries_version_path_and_text():
    data = json.loads(run("--json", "guide").output)
    assert data["version"] == cli_guide.__version__
    assert pathlib.Path(data["path"]) == REPO / "AGENTS.md"
    assert data["text"] == (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "text" not in json.loads(run("--json", "guide", "--path").output)


def test_the_copy_inside_the_package_wins(tmp_path, monkeypatch):
    package = tmp_path / "site-packages" / "contao_ai_cli"
    package.mkdir(parents=True)
    (package / "AGENTS.md").write_text("packaged", encoding="utf-8")
    (package.parent / "AGENTS.md").write_text("stray", encoding="utf-8")
    monkeypatch.setattr(cli_guide, "_PACKAGE_DIR", package)
    assert run("guide").output == "packaged"


def test_missing_guide_fails_and_says_where_to_find_it(tmp_path, monkeypatch):
    package = tmp_path / "contao_ai_cli"
    package.mkdir()
    monkeypatch.setattr(cli_guide, "_PACKAGE_DIR", package)
    result = run("guide")
    assert result.exit_code == 1
    assert "github.com/webwerkwien/contao-ai-cli/blob/main/AGENTS.md" in result.output
    assert f"pipx install --force git+https://github.com/webwerkwien/contao-ai-cli.git@v{cli_guide.__version__}" in result.output


def test_guide_triggers_no_update_check():
    # Purely local; an SSH round trip to print a file would be absurd.
    assert "guide" in update_notice.SKIPPED


def test_agents_md_names_every_command_the_notice_skips():
    text = " ".join((REPO / "AGENTS.md").read_text(encoding="utf-8").split())
    start = text.index("Skipped for ")
    sentence = text[start:text.index("--help", start)]
    names = [n for n in update_notice.SKIPPED if n]
    assert len(names) == 8
    for name in names:
        assert f"`{name}`" in sentence, f"AGENTS.md does not say the notice skips `{name}`"
    assert "`page`" not in sentence  # known non-match: an ordinary command is not listed


def test_the_build_copies_the_guide_into_the_package(tmp_path, monkeypatch):
    # Skipped where setuptools is absent (the suite's own Python has none); the
    # release round builds a wheel and checks its contents as well.
    pytest.importorskip("setuptools")
    from setuptools.dist import Distribution

    # Everything in setup.py before the setup() call: the imports and the class.
    source = (REPO / "setup.py").read_text(encoding="utf-8").split("\nsetup(")[0]
    ns = {"__file__": str(REPO / "setup.py"), "__name__": "setup_under_test"}
    exec(compile(source, str(REPO / "setup.py"), "exec"), ns)

    monkeypatch.chdir(REPO)
    dist = Distribution({"name": "contao-ai-cli", "packages": ["contao_ai_cli"]})
    dist.script_name = "setup.py"  # set by setup() in a real build; distutils needs it
    build = ns["BuildWithGuide"](dist)
    build.build_lib = str(tmp_path)
    build.ensure_finalized()
    build.run()

    target = tmp_path / "contao_ai_cli" / "AGENTS.md"
    assert target.read_bytes() == (REPO / "AGENTS.md").read_bytes()
    assert str(target) in build.get_outputs()
    assert build.get_output_mapping()[str(target)] == str(REPO / "AGENTS.md")


def test_claude_md_only_imports_the_shared_guide():
    text = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in text
    assert len(text.splitlines()) < 5
