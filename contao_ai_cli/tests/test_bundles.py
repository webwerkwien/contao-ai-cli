"""Installing a bundle is its own command now -- and writing composer.json its own consent."""
from unittest.mock import MagicMock, patch

from contao_ai_cli.core import bundles

MANAGED = {"phar_path": "public/contao-manager.phar.php", "config_dir": True, "manager_bundle": True, "available": True}
STANDALONE = {"phar_path": None, "config_dir": False, "manager_bundle": False, "available": False}
CORE = "webwerkwien/contao-ai-core-bundle"


def backend():
    b = MagicMock()
    b.php_path = "php"
    b.run_raw.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    b.run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    return b


def versions(*answers):
    return patch.object(bundles, "get_installed_package_versions",
                        side_effect=[{CORE: a} for a in answers])


def test_without_manager_and_missing_plugins_nothing_is_written():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=STANDALONE), \
         patch.object(bundles, "get_missing_allow_plugins", return_value=["contao/manager-plugin"]), \
         patch.object(bundles, "set_allow_plugins") as set_plugins, versions(None):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error"
    assert result["missingAllowPlugins"] == ["contao/manager-plugin"]
    assert "--allow-plugins" in result["message"]
    set_plugins.assert_not_called()
    b.run_raw.assert_not_called()


def test_an_update_without_manager_is_refused_the_same_way():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=STANDALONE), \
         patch.object(bundles, "get_missing_allow_plugins", return_value=["contao/manager-plugin"]), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.19.0"), \
         patch.object(bundles, "set_allow_plugins") as set_plugins, versions("v0.18.0"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["status"] == "error" and result["missingAllowPlugins"] == ["contao/manager-plugin"]
    set_plugins.assert_not_called()
    b.run_raw.assert_not_called()


def test_allow_plugins_writes_them_and_installs():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=STANDALONE), \
         patch.object(bundles, "get_missing_allow_plugins", return_value=["contao/manager-plugin"]), \
         patch.object(bundles, "set_allow_plugins") as set_plugins, versions(None, "v0.19.0"):
        result = bundles.install_bundle(b, "core", "install", allow_plugins=True)
    set_plugins.assert_called_once_with(b, ["contao/manager-plugin"])
    assert result["status"] == "ok" and result["installed"] == "v0.19.0"
    assert result["allowPluginsWritten"] == ["contao/manager-plugin"]


def test_the_manager_passthrough_never_touches_composer_json():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_missing_allow_plugins") as missing, versions(None, "v0.19.0"):
        result = bundles.install_bundle(b, "core", "install")
    missing.assert_not_called()
    assert "contao-manager.phar.php composer require" in b.run_raw.call_args.args[0]
    assert result["via"] == "contao-manager"


def test_success_is_only_what_can_be_read_back():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, None):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error"
    assert "not installed afterwards" in result["message"]


def test_an_installed_bundle_is_not_installed_again():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions("v0.19.0"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "ok" and result["changed"] is False
    b.run_raw.assert_not_called()


def test_update_of_a_missing_bundle_points_to_install():
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None):
        result = bundles.install_bundle(backend(), "core", "update")
    assert result["status"] == "error" and "bundle install core" in result["message"]


def test_update_when_up_to_date_runs_no_composer():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions("v0.19.0"), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.19.0"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["changed"] is False
    b.run_raw.assert_not_called()


def test_the_backend_bundle_uses_its_own_package_and_constraint():
    b = backend()
    backend_pkg = "webwerkwien/contao-ai-backend-bundle"
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_installed_package_versions",
                      side_effect=[{backend_pkg: None}, {backend_pkg: "v0.3.0"}]):
        bundles.install_bundle(b, "backend", "install")
    # shlex.quote wraps the constraint (space, <, >) in single quotes
    assert "'webwerkwien/contao-ai-backend-bundle:>=0.1 <1.0'" in b.run_raw.call_args.args[0]


def test_a_composer_failure_is_an_answer_not_a_traceback():
    from contao_ai_cli.utils.contao_backend import ContaoBackendError
    b = backend()
    b.run_raw.side_effect = ContaoBackendError("composer exploded")
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error" and "composer exploded" in result["message"]


def test_update_crosses_a_minor_via_require_with_the_latest_constraint():
    """review 2026-09-17: a plain `composer update` never leaves the ^0.19 that
    the first `require` wrote, so an update could never cross a 0.x minor."""
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.20.0"), \
         versions("v0.19.0", "v0.20.0"):
        result = bundles.install_bundle(b, "core", "update")
    cmd = b.run_raw.call_args.args[0]
    assert "composer require" in cmd
    assert "composer update" not in cmd
    assert "'webwerkwien/contao-ai-core-bundle:^0.20.0'" in cmd
    assert result["status"] == "ok" and result["installed"] == "v0.20.0"


def test_backend_update_keeps_its_range_requirement_via_require():
    b = backend()
    backend_pkg = "webwerkwien/contao-ai-backend-bundle"
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.3.0"), \
         patch.object(bundles, "get_installed_package_versions",
                      side_effect=[{backend_pkg: "v0.2.0"}, {backend_pkg: "v0.3.0"}]):
        result = bundles.install_bundle(b, "backend", "update")
    cmd = b.run_raw.call_args.args[0]
    assert "composer require" in cmd
    assert "'webwerkwien/contao-ai-backend-bundle:>=0.1 <1.0'" in cmd
    assert result["status"] == "ok"


def test_update_reports_error_when_the_installed_version_does_not_match_latest():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.20.0"), \
         versions("v0.19.0", "v0.19.5"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["status"] == "error"
    assert "0.19.5" in result["message"] and "0.20.0" in result["message"]


def test_update_with_packagist_unreachable_is_an_error_not_up_to_date():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value=None), \
         versions("v0.19.0"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["status"] == "error"
    assert "Packagist" in result["message"]
    b.run_raw.assert_not_called()


def test_server_unreachable_is_reported_before_anything_else():
    """review 2026-09-17: every helper below this swallows ContaoBackendError, so
    an unreachable server used to fall through to the allow-plugins refusal."""
    from contao_ai_cli.utils.contao_backend import ContaoBackendError
    b = backend()
    b.run.side_effect = ContaoBackendError("Connection refused")
    with patch.object(bundles, "detect_contao_manager") as detect, \
         patch.object(bundles, "get_installed_package_versions") as get_versions:
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error" and result["code"] == 1
    assert "server not reachable" in result["message"]
    detect.assert_not_called()
    get_versions.assert_not_called()
    b.run_raw.assert_not_called()
