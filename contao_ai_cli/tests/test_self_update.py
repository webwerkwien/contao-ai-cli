"""
Tests for the `self-update` command.

Covers: already up to date (no install attempted), an update reported only
when pipx confirms it, the message after a successful update, missing pipx,
and GitHub being unreachable (which must not read as "up to date").
"""
import json
from unittest.mock import patch

from click.testing import CliRunner

from contao_ai_cli.cli import cli_self_update as mod


def run():
    return CliRunner().invoke(mod.self_update, ["--json"], obj={})


def test_up_to_date_installs_nothing():
    with patch.object(mod, "check_cli_update", return_value={"current": "0.21.0", "latest": "0.21.0", "update_available": False}), \
         patch.object(mod, "install_cli_update") as install:
        result = run()
    assert result.exit_code == 0 and json.loads(result.stdout)["changed"] is False
    install.assert_not_called()


def test_an_update_is_reported_only_when_pipx_shows_it():
    with patch.object(mod, "check_cli_update", return_value={"current": "0.21.0", "latest": "0.22.0", "update_available": True}), \
         patch.object(mod.shutil, "which", return_value="pipx"), \
         patch.object(mod, "install_cli_update", return_value={"installed": "0.21.0", "updated": False}):
        result = run()
    assert result.exit_code == 1
    assert "pipx install --force" in json.loads(result.stdout)["message"]


def test_a_successful_update_says_a_running_repl_keeps_the_old_code():
    with patch.object(mod, "check_cli_update", return_value={"current": "0.21.0", "latest": "0.22.0", "update_available": True}), \
         patch.object(mod.shutil, "which", return_value="pipx"), \
         patch.object(mod, "install_cli_update", return_value={"installed": "0.22.0", "updated": True}):
        out = json.loads(run().stdout)
    assert out["installed"] == "0.22.0" and "repl" in out["message"]


def test_missing_pipx_names_how_to_get_it():
    with patch.object(mod, "check_cli_update", return_value={"current": "0.21.0", "latest": "0.22.0", "update_available": True}), \
         patch.object(mod.shutil, "which", return_value=None):
        result = run()
    assert result.exit_code == 1 and "python -m pip install --user pipx" in json.loads(result.stdout)["message"]


def test_unreachable_github_is_an_error_not_up_to_date():
    with patch.object(mod, "check_cli_update", return_value={"current": "0.21.0", "latest": None, "update_available": False}):
        result = run()
    assert result.exit_code == 1
