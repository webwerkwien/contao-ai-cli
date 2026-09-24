"""
Installing an extension this CLI does not manage — issues #57 and #58.

Nothing the project shipped told a caller how. The Contao Manager passthrough was
described only as the internals of `bundle install core|backend`, `bundle install
<anything else>` answered Click's generic `invalid choice`, and the guide said
firmly not to go around the CLI without ever saying where the legitimate boundary
runs. A parallel session found the right route only by reading a private
maintenance note that no user of this CLI has (2026-09-24).

These tests pin the two halves of the answer: the refusal that points somewhere,
and the `composer` key that spares the caller from guessing the command.
"""
import pathlib
import re
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from contao_ai_cli.cli import cli_bundle
from contao_ai_cli.core.bundles import composer_command
from contao_ai_cli.core.status import collect_status

REPO = pathlib.Path(__file__).resolve().parent.parent.parent


class TestTheRefusalIsASignpost:
    def _run(self, name):
        return CliRunner().invoke(cli_bundle.bundle, ["install", name], obj={})

    def test_a_foreign_package_is_refused(self):
        assert self._run("terminal42/contao-changelanguage").exit_code != 0

    def test_the_refusal_says_what_to_do_instead(self):
        out = self._run("terminal42/contao-changelanguage").output
        assert "contao-manager.phar.php composer require" in out
        assert "--dry-run" in out
        assert "health --json" in out
        assert "schema sync" in out

    def test_the_refusal_repeats_the_package_the_caller_asked_for(self):
        """A generic message leaves the caller to work out what it refused."""
        out = self._run("terminal42/contao-changelanguage").output
        assert "terminal42/contao-changelanguage" in out

    @pytest.mark.parametrize("name", ["core", "backend"])
    def test_our_own_two_still_go_through(self, name):
        with patch("contao_ai_cli.cli.cli_bundle.bundles_mod") as mod:
            mod.BUNDLES = {"core": "webwerkwien/contao-ai-core-bundle",
                           "backend": "webwerkwien/contao-ai-backend-bundle"}
            mod.install_bundle.return_value = {"status": "ok", "changed": False}
            with patch("contao_ai_cli.cli.cli_bundle._get_backend"):
                CliRunner().invoke(cli_bundle.bundle, ["install", name], obj={})
        assert mod.install_bundle.call_args[0][1] == name

    def test_the_full_package_name_of_one_of_ours_resolves(self):
        """`bundle install webwerkwien/contao-ai-core-bundle` is an obvious thing to type."""
        assert cli_bundle._resolve("webwerkwien/contao-ai-core-bundle") == "core"


class TestHealthNamesTheComposerRoute:
    def _status(self, tmp_path, manager_available, phar="public/contao-manager.phar.php",
                manager_bundle=True):
        backend = MagicMock()
        backend.php_path = "/usr/bin/php8.3"
        with patch("contao_ai_cli.core.status.check_cli_update",
                   return_value={"current": "1.1.0", "latest": "1.1.0", "update_available": False}), \
             patch("contao_ai_cli.core.status.ContaoBackend.from_session", return_value=backend), \
             patch("contao_ai_cli.core.status.get_installed_package_versions",
                   return_value={"webwerkwien/contao-ai-core-bundle": "1.1.0",
                                 "webwerkwien/contao-ai-backend-bundle": None,
                                 "contao/core-bundle": "5.7.13"}), \
             patch("contao_ai_cli.core.status.get_bundle_latest_version", return_value="1.1.0"), \
             patch("contao_ai_cli.core.status.detect_contao_manager",
                   return_value={"phar_path": phar,
                                 "config_dir": manager_available,
                                 "manager_bundle": manager_bundle,
                                 "available": manager_available}):
            return collect_status(str(tmp_path / "none.json"))

    def test_a_phar_that_cannot_be_driven_is_not_reported_as_no_manager(self, tmp_path):
        """Issue #59: unlike bundle install, this advice has no allow-plugins net behind it.

        Measured 2026-09-24: none of the five reachable installations is in this
        state. The test exists because the *consequence* is a plain `composer
        require` on a Managed Edition, written past the manager.
        """
        composer = self._status(tmp_path, manager_available=False)["composer"]
        assert composer["via"] == "composer"
        assert composer["managerPhar"] == "public/contao-manager.phar.php"
        assert "phar is present" in composer["note"]
        assert "past the manager" in composer["note"]

    def test_a_managed_edition_without_the_tool_says_so(self, tmp_path):
        """The state c5-contao53 and c5-contao6 are actually in (measured 2026-09-24)."""
        composer = self._status(tmp_path, manager_available=False, phar=None,
                                manager_bundle=True)["composer"]
        assert composer["via"] == "composer"
        assert composer["managerPhar"] is None and composer["managerBundle"] is True
        assert "Managed Edition" in composer["note"]
        assert "the right one" in composer["note"]

    def test_the_text_output_no_longer_claims_there_is_no_manager(self, tmp_path):
        """The old line said "no Contao Manager found", which was wrong in both cases above."""
        from contao_ai_cli.cli import cli_health
        from click.testing import CliRunner as _CliRunner
        state = self._status(tmp_path, manager_available=False)
        with patch("contao_ai_cli.cli.cli_health.collect_status", return_value=state):
            out = _CliRunner().invoke(cli_health.health, [], obj={}).output
        assert "no Contao Manager found" not in out
        assert "phar is present" in out

    def test_a_managed_edition_answers_the_passthrough(self, tmp_path):
        composer = self._status(tmp_path, manager_available=True)["composer"]
        assert composer["via"] == "contao-manager"
        assert composer["command"] == "/usr/bin/php8.3 public/contao-manager.phar.php composer"
        assert "note" not in composer

    def test_without_a_manager_it_answers_plain_composer(self, tmp_path):
        composer = self._status(tmp_path, manager_available=False, phar=None,
                                manager_bundle=False)["composer"]
        assert composer["via"] == "composer"
        assert composer["command"] == "composer"
        assert "note" not in composer

    def test_an_unreachable_server_says_it_could_not_look(self, tmp_path):
        """`via: null` must not read as "this site has no Composer"."""
        with patch("contao_ai_cli.core.status.check_cli_update",
                   return_value={"current": "1.1.0", "latest": None, "update_available": False}):
            composer = collect_status(str(tmp_path / "none.json"))["composer"]
        assert composer == {"via": None, "command": None,
                            "managerPhar": None, "managerBundle": None}

    def test_the_reported_command_is_the_one_we_would_run(self):
        """Two copies of this string would be a documented command we do not execute."""
        backend = MagicMock()
        backend.php_path = "/usr/bin/php8.3"
        phar = "public/contao-manager.phar.php"
        assert composer_command(backend, phar) == f"/usr/bin/php8.3 {phar} composer"
        assert composer_command(backend, None) == "composer"

    def test_a_phar_path_that_needs_quoting_is_quoted(self):
        backend = MagicMock()
        backend.php_path = "/usr/bin/php 8.3"
        assert composer_command(backend, "web/my dir/cm.phar.php") == \
            "'/usr/bin/php 8.3' 'web/my dir/cm.phar.php' composer"


class TestTheGuideSaysWhereTheBoundaryRuns:
    """The code half is worthless if the guide still leaves the question unanswered."""

    def test_agents_md_has_the_section(self):
        text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        assert "### Installing an extension this CLI does not manage" in text

    def test_readme_has_the_section(self):
        text = (REPO / "README.md").read_text(encoding="utf-8")
        assert "### Installing an extension this CLI does not manage" in text

    @pytest.mark.parametrize("doc", ["AGENTS.md", "README.md"])
    def test_the_section_names_the_dry_run_and_the_stale_schema(self, doc):
        text = (REPO / doc).read_text(encoding="utf-8")
        section = text.split("Installing an extension this CLI does not manage", 1)[1]
        section = re.split(r"\n### ", section, maxsplit=1)[0]
        assert "--dry-run" in section
        assert "schema sync" in section
        assert "allow-plugins" in section

    def test_agents_md_states_that_this_is_outside_the_cli(self):
        """Without this sentence the "do not go around this CLI" rule reads as covering it."""
        text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        section = text.split("Installing an extension this CLI does not manage", 1)[1]
        section = re.split(r"\n### ", section, maxsplit=1)[0]
        assert "outside this CLI" in section
        assert "None of it happens if you go around this CLI" in section
