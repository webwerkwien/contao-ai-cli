"""
Tests for the composer path of the connect flow.

Managed Editions must go through the Contao Manager's composer passthrough so the
project composer.json is never touched behind the user's back; only the plain-composer
fallback may write allow-plugins, and only after an explicit yes.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli.cli_connect import _install_core_bundle, connect
from contao_ai_cli.cli.helpers import (
    composer_core_bundle, detect_contao_manager, get_missing_allow_plugins,
    install_cli_update, set_allow_plugins,
)
from contao_ai_cli.utils.contao_backend import ContaoBackendError


def make_backend(stdout="", php_path="php"):
    backend = MagicMock()
    backend.php_path = php_path
    backend.run_raw.return_value = {"returncode": 0, "stdout": stdout, "stderr": ""}
    backend.run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    return backend


MANAGED = {"phar_path": "public/contao-manager.phar.php", "config_dir": True,
           "manager_bundle": True, "available": True}
STANDALONE = {"phar_path": None, "config_dir": False,
              "manager_bundle": False, "available": False}


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
        composer_core_bundle(backend, "require", "public/contao-manager.phar.php")
        cmd = backend.run_raw.call_args[0][0]
        assert cmd.startswith("/opt/php-8.3/bin/php public/contao-manager.phar.php composer require")
        assert "webwerkwien/contao-ai-core-bundle" in cmd
        assert "--no-interaction" in cmd

    def test_manager_path_never_configures_allow_plugins(self):
        """The whole point: the project composer.json config is left alone."""
        backend = make_backend()
        composer_core_bundle(backend, "update", "public/contao-manager.phar.php")
        assert "composer config" not in backend.run_raw.call_args[0][0]

    def test_fallback_uses_plain_composer(self):
        backend = make_backend()
        composer_core_bundle(backend, "require")
        assert backend.run_raw.call_args[0][0].startswith(
            "composer require webwerkwien/contao-ai-core-bundle"
        )

    def test_rejects_unknown_action(self):
        with pytest.raises(ValueError):
            composer_core_bundle(make_backend(), "remove")


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


class TestInstallCoreBundle:
    def test_managed_edition_installs_without_asking_or_writing(self):
        """No extra prompt, no allow-plugins write — the phar carries the config."""
        backend = make_backend()
        with patch("contao_ai_cli.cli.cli_connect.click.confirm") as confirm, \
             patch("contao_ai_cli.cli.cli_connect.set_allow_plugins") as setter, \
             patch("contao_ai_cli.cli.cli_connect.composer_core_bundle") as composer:
            assert _install_core_bundle(backend, MANAGED, "require") is True
        confirm.assert_not_called()
        setter.assert_not_called()
        composer.assert_called_once_with(backend, "require", "public/contao-manager.phar.php")

    def test_fallback_asks_before_writing_composer_json(self):
        backend = make_backend()
        with patch("contao_ai_cli.cli.cli_connect.get_missing_allow_plugins",
                   return_value=["contao/manager-plugin"]), \
             patch("contao_ai_cli.cli.cli_connect.click.confirm", return_value=True) as confirm, \
             patch("contao_ai_cli.cli.cli_connect.set_allow_plugins") as setter, \
             patch("contao_ai_cli.cli.cli_connect.composer_core_bundle") as composer:
            assert _install_core_bundle(backend, STANDALONE, "require") is True
        assert confirm.call_args.kwargs["default"] is False
        setter.assert_called_once_with(backend, ["contao/manager-plugin"])
        composer.assert_called_once_with(backend, "require", None)

    def test_declining_aborts_before_any_composer_call(self):
        backend = make_backend()
        with patch("contao_ai_cli.cli.cli_connect.get_missing_allow_plugins",
                   return_value=["contao/manager-plugin"]), \
             patch("contao_ai_cli.cli.cli_connect.click.confirm", return_value=False), \
             patch("contao_ai_cli.cli.cli_connect.set_allow_plugins") as setter, \
             patch("contao_ai_cli.cli.cli_connect.composer_core_bundle") as composer:
            assert _install_core_bundle(backend, STANDALONE, "require") is False
        setter.assert_not_called()
        composer.assert_not_called()

    def test_fallback_skips_the_question_when_plugins_already_allowed(self):
        backend = make_backend()
        with patch("contao_ai_cli.cli.cli_connect.get_missing_allow_plugins", return_value=[]), \
             patch("contao_ai_cli.cli.cli_connect.click.confirm") as confirm, \
             patch("contao_ai_cli.cli.cli_connect.set_allow_plugins") as setter, \
             patch("contao_ai_cli.cli.cli_connect.composer_core_bundle"):
            assert _install_core_bundle(backend, STANDALONE, "require") is True
        confirm.assert_not_called()
        setter.assert_not_called()

    def test_composer_failure_is_reported_not_raised(self):
        backend = make_backend()
        with patch("contao_ai_cli.cli.cli_connect.composer_core_bundle",
                   side_effect=ContaoBackendError("network down")):
            assert _install_core_bundle(backend, MANAGED, "update") is False


class TestConnectDefaults:
    def test_pressing_enter_does_not_install_the_bundle(self, tmp_path):
        """The install prompt defaults to no — an absent-minded Enter must be a no-op."""
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps({"host": "h", "user": "u", "contao_root": "/r"}),
                                encoding="utf-8")
        with patch("contao_ai_cli.cli.cli_connect.ContaoBackend") as backend_cls, \
             patch("contao_ai_cli.cli.cli_connect.session_mod") as sessions, \
             patch("contao_ai_cli.cli.cli_connect.check_cli_update",
                   return_value={"current": "0.0.0", "latest": None, "update_available": False}), \
             patch("contao_ai_cli.cli.cli_connect.get_core_bundle_installed_version",
                   return_value=None), \
             patch("contao_ai_cli.cli.cli_connect.detect_contao_manager", return_value=MANAGED), \
             patch("contao_ai_cli.cli.cli_connect.composer_core_bundle") as composer:
            sessions.get_session_path.return_value = str(session_path)
            sessions.save_session.return_value = str(session_path)
            backend_cls.return_value.run.return_value = {"stdout": "Contao 5.7"}
            result = CliRunner().invoke(
                connect,
                ["--host", "h", "--user", "u", "--root", "/r"],
                # continue -> yes, database backup -> no, install bundle -> just Enter
                input="y\nn\n\n",
                obj={},
            )
        assert result.exit_code == 0, result.output
        composer.assert_not_called()
        assert json.loads(session_path.read_text(encoding="utf-8"))["bridge_available"] is False


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

    def test_missing_pipx_is_not_a_crash(self):
        with patch("contao_ai_cli.cli.helpers.subprocess.run",
                   side_effect=FileNotFoundError),              patch("contao_ai_cli.cli.helpers.get_pipx_installed_version",
                   return_value="0.4.2"):
            assert install_cli_update("0.4.3")["updated"] is False
