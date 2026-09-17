"""
Tests for the composer path of the connect flow.

Managed Editions must go through the Contao Manager's composer passthrough so the
project composer.json is never touched behind the user's back; only the plain-composer
fallback may write allow-plugins, and only after an explicit yes.
"""
from unittest.mock import MagicMock, patch

import pytest

from contao_ai_cli.cli.helpers import (
    CORE_BUNDLE, detect_contao_manager, get_missing_allow_plugins,
    get_launcher_version, install_cli_update, set_allow_plugins,
)
from contao_ai_cli.core.bundles import composer_bundle
from contao_ai_cli.utils.contao_backend import ContaoBackendError


def make_backend(stdout="", php_path="php"):
    backend = MagicMock()
    backend.php_path = php_path
    backend.run_raw.return_value = {"returncode": 0, "stdout": stdout, "stderr": ""}
    backend.run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    return backend


class TestDetectContaoManager:
    def test_detects_managed_edition(self):
        """phar in public/ plus the manager config dir means the passthrough is usable."""
        backend = make_backend(
            "phar=public/contao-manager.phar.php\nconfig_dir=1\nmanager_bundle=1"
        )
        result = detect_contao_manager(backend)
        assert result["available"] is True
        assert result["phar_path"] == "public/contao-manager.phar.php"
        assert result["manager_bundle"] is True

    def test_detects_legacy_web_dir_phar(self):
        """Installations carried over from Contao 4 keep the phar in web/."""
        backend = make_backend("phar=web/contao-manager.phar.php\nconfig_dir=1")
        result = detect_contao_manager(backend)
        assert result["available"] is True
        assert result["phar_path"] == "web/contao-manager.phar.php"

    def test_phar_without_config_dir_is_not_available(self):
        """Without the manager's own config dir there is no allow-plugins config to rely on."""
        backend = make_backend("phar=public/contao-manager.phar.php")
        assert detect_contao_manager(backend)["available"] is False

    def test_manager_bundle_alone_is_not_enough(self):
        """contao/manager-bundle in the lock corroborates, but there is no phar to call."""
        backend = make_backend("config_dir=1\nmanager_bundle=1")
        result = detect_contao_manager(backend)
        assert result["available"] is False
        assert result["phar_path"] is None

    def test_ssh_failure_falls_back_to_not_available(self):
        """A failing probe must not be read as 'managed'."""
        backend = make_backend()
        backend.run_raw.side_effect = ContaoBackendError("boom")
        assert detect_contao_manager(backend)["available"] is False

    def test_probe_is_a_single_round_trip(self):
        """Detection costs one SSH call, not four."""
        backend = make_backend("phar=public/contao-manager.phar.php\nconfig_dir=1")
        detect_contao_manager(backend)
        assert backend.run_raw.call_count == 1


class TestComposerCoreBundle:
    def test_manager_path_uses_phar_and_session_php_binary(self):
        """The phar must be invoked with the PHP binary from the session, not a bare 'php'."""
        backend = make_backend(php_path="/opt/php-8.3/bin/php")
        composer_bundle(backend, CORE_BUNDLE, "require", "public/contao-manager.phar.php")
        cmd = backend.run_raw.call_args[0][0]
        assert cmd.startswith("/opt/php-8.3/bin/php public/contao-manager.phar.php composer require")
        assert "webwerkwien/contao-ai-core-bundle" in cmd
        assert "--no-interaction" in cmd

    def test_manager_path_never_configures_allow_plugins(self):
        """The whole point: the project composer.json config is left alone."""
        backend = make_backend()
        composer_bundle(backend, CORE_BUNDLE, "update", "public/contao-manager.phar.php")
        assert "composer config" not in backend.run_raw.call_args[0][0]

    def test_fallback_uses_plain_composer(self):
        backend = make_backend()
        composer_bundle(backend, CORE_BUNDLE, "require")
        assert backend.run_raw.call_args[0][0].startswith(
            "composer require webwerkwien/contao-ai-core-bundle"
        )

    def test_rejects_unknown_action(self):
        with pytest.raises(ValueError):
            composer_bundle(make_backend(), CORE_BUNDLE, "remove")


class TestAllowPlugins:
    def test_wildcard_means_nothing_missing(self):
        assert get_missing_allow_plugins(make_backend("*")) == []

    def test_reports_only_the_unallowed_plugins(self):
        backend = make_backend("contao/manager-plugin")
        assert get_missing_allow_plugins(backend) == ["contao-components/installer"]

    def test_empty_config_reports_all(self):
        assert get_missing_allow_plugins(make_backend("")) == [
            "contao-components/installer", "contao/manager-plugin",
        ]

    def test_uses_session_php_binary(self):
        backend = make_backend("*", php_path="/opt/php-8.3/bin/php")
        get_missing_allow_plugins(backend)
        assert backend.run_raw.call_args[0][0].startswith("/opt/php-8.3/bin/php -r")

    def test_set_allow_plugins_writes_only_the_given_plugins(self):
        backend = make_backend()
        set_allow_plugins(backend, ["contao/manager-plugin"])
        cmds = [c[0][0] for c in backend.run_raw.call_args_list]
        assert cmds == ["composer config allow-plugins.contao/manager-plugin true"]


class TestInstallCliUpdate:
    """
    'pipx upgrade' is a no-op on a tag-pinned spec: 'git+…@v0.4.1' resolves to
    v0.4.1 forever and pipx reports "already at latest version". The old flow ran
    it and printed success regardless.
    """

    def test_forces_a_reinstall_at_the_requested_tag(self):
        with patch("contao_ai_cli.cli.helpers.subprocess.run") as run,              patch("contao_ai_cli.cli.helpers.get_pipx_installed_version",
                   return_value="0.4.3"):
            result = install_cli_update("0.4.3")
        argv = run.call_args[0][0]
        assert argv[:3] == ["pipx", "install", "--force"]
        assert argv[3].endswith("@v0.4.3")
        assert result == {"installed": "0.4.3", "updated": True}

    def test_never_calls_pipx_upgrade(self):
        with patch("contao_ai_cli.cli.helpers.subprocess.run") as run,              patch("contao_ai_cli.cli.helpers.get_pipx_installed_version",
                   return_value="0.4.3"):
            install_cli_update("v0.4.3")
        assert "upgrade" not in run.call_args[0][0]

    def test_reports_failure_when_the_version_did_not_move(self):
        """The bug that hid for a whole release: pipx ran, nothing changed, success printed."""
        with patch("contao_ai_cli.cli.helpers.subprocess.run"),              patch("contao_ai_cli.cli.helpers.get_pipx_installed_version",
                   return_value="0.4.2"):
            assert install_cli_update("0.4.3") == {"installed": "0.4.2", "updated": False}

    def test_a_failed_install_keeps_the_reason_pipx_gave(self):
        """Review 2026-09-17: capturing pipx's output hid why an install failed."""
        failed = MagicMock(stderr="fatal: unable to access github.com\n")
        with patch("contao_ai_cli.cli.helpers.subprocess.run", return_value=failed), \
             patch("contao_ai_cli.cli.helpers.get_pipx_installed_version", return_value="0.4.2"):
            outcome = install_cli_update("0.4.3")
        assert outcome["updated"] is False
        assert "unable to access github.com" in outcome["reason"]

    def test_when_pipx_cannot_answer_the_new_launcher_is_asked(self):
        """Nr. 54, measured 2026-09-17 with an instrumented 0.22.9 updating to 0.23.0 on
        Windows: pipx moves the running `contao-ai-cli.exe` into its trash, the running
        self-update keeps it locked, and every later pipx call fails emptying that trash
        (`PermissionError: [WinError 5] … pipx\\trash\\….contao-ai-cli.exe`) — so
        `pipx list --json` answers nothing for as long as this process lives. Retrying
        (v0.23.0) could never help. The launcher pipx just wrote is not locked."""
        with patch("contao_ai_cli.cli.helpers.subprocess.run"), \
             patch("contao_ai_cli.cli.helpers.get_pipx_installed_version", return_value=None), \
             patch("contao_ai_cli.cli.helpers.get_launcher_version", return_value="0.4.3"):
            assert install_cli_update("0.4.3") == {"installed": "0.4.3", "updated": True}

    def test_the_launcher_is_not_asked_when_pipx_answers(self):
        with patch("contao_ai_cli.cli.helpers.subprocess.run"), \
             patch("contao_ai_cli.cli.helpers.get_pipx_installed_version", return_value="0.4.3"), \
             patch("contao_ai_cli.cli.helpers.get_launcher_version") as launcher:
            assert install_cli_update("0.4.3")["updated"] is True
        launcher.assert_not_called()

    def test_a_failing_launcher_is_no_version(self):
        broken = MagicMock(returncode=1, stdout="")
        with patch("contao_ai_cli.cli.helpers.shutil.which", return_value="contao-ai-cli"), \
             patch("contao_ai_cli.cli.helpers.subprocess.run", return_value=broken):
            assert get_launcher_version() is None

    def test_a_version_nobody_can_report_still_fails(self):
        with patch("contao_ai_cli.cli.helpers.subprocess.run"), \
             patch("contao_ai_cli.cli.helpers.get_pipx_installed_version", return_value=None), \
             patch("contao_ai_cli.cli.helpers.get_launcher_version", return_value=None):
            assert install_cli_update("0.4.3")["updated"] is False

    def test_the_launcher_version_is_read_from_its_version_line(self):
        answer = MagicMock(returncode=0, stdout="contao-ai-cli, version 0.23.0\n")
        with patch("contao_ai_cli.cli.helpers.shutil.which", return_value=r"C:\bin\contao-ai-cli.exe"), \
             patch("contao_ai_cli.cli.helpers.subprocess.run", return_value=answer) as run:
            assert get_launcher_version() == "0.23.0"
        assert run.call_args[0][0] == [r"C:\bin\contao-ai-cli.exe", "--version"]

    def test_no_launcher_on_the_path_is_no_version(self):
        with patch("contao_ai_cli.cli.helpers.shutil.which", return_value=None):
            assert get_launcher_version() is None

    def test_missing_pipx_is_not_a_crash(self):
        with patch("contao_ai_cli.cli.helpers.subprocess.run",
                   side_effect=FileNotFoundError),              patch("contao_ai_cli.cli.helpers.get_pipx_installed_version",
                   return_value="0.4.2"):
            assert install_cli_update("0.4.3")["updated"] is False

    def test_pipx_output_is_captured_not_printed(self):
        """review 2026-09-17: pipx writing to stdout broke `self-update --json`."""
        with patch("contao_ai_cli.cli.helpers.subprocess.run") as run, \
             patch("contao_ai_cli.cli.helpers.get_pipx_installed_version", return_value="0.4.3"):
            install_cli_update("0.4.3")
        assert run.call_args.kwargs.get("capture_output") is True
