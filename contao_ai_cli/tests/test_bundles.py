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


def composer_calls(b):
    """The Composer commands among the SSH calls -- the package snapshots run there too."""
    return [c.args[0] for c in b.run_raw.call_args_list if " composer " in f" {c.args[0]} "]


def composer_cmd(b):
    calls = composer_calls(b)
    assert len(calls) == 1, calls
    return calls[0]


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
    assert "contao-manager.phar.php composer require" in composer_cmd(b)
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
    assert "'webwerkwien/contao-ai-backend-bundle:>=0.1 <2.0'" in composer_cmd(b)


def test_a_composer_failure_is_an_answer_not_a_traceback():
    from contao_ai_cli.utils.contao_backend import ContaoBackendError
    b = backend()
    b.run_raw.side_effect = ContaoBackendError("composer exploded")
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error" and "composer exploded" in result["message"]


def test_update_crosses_into_1x_via_require_with_the_readme_constraint():
    """On a live installation, 2026-09-17 (Nr. 52): v0.21.1 required `^0.20.0` and so
    overwrote the house constraint `>=0.2 <1.0` -- the next minor would again be out of
    reach for the Contao Manager and `composer update`. Since v1.0.0 the core bundle is 1.x:
    a site on `>=0.2 <1.0` gets `^1.0` on its next update, which reaches every 1.x minor."""
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="1.0.0"), \
         versions("v0.27.0", "v1.0.0"):
        result = bundles.install_bundle(b, "core", "update")
    cmd = composer_cmd(b)
    assert "composer require" in cmd
    assert "composer update" not in cmd
    # The constraint the core-bundle README recommends.
    assert "'webwerkwien/contao-ai-core-bundle:^1.0'" in cmd
    assert "<1.0" not in cmd and "^0." not in cmd
    assert result["status"] == "ok" and result["installed"] == "v1.0.0"
    assert result["constraint"] == "^1.0"


def test_install_writes_the_readme_constraint_too():
    """A plain `composer require <pkg>` would write `^<latest>` -- the constraint is explicit."""
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.0.0"):
        result = bundles.install_bundle(b, "core", "install")
    assert "'webwerkwien/contao-ai-core-bundle:^1.0'" in composer_cmd(b)
    assert result["constraint"] == "^1.0"


def test_an_update_held_back_says_what_did_change():
    """Pre-release review 2026-09-17: Composer exits 0 with an older version when e.g. the
    newest release needs a newer PHP -- composer.json and the lock were rewritten anyway,
    so "nothing else was changed" was false."""
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.20.0"), \
         versions("v0.19.0", "v0.19.5"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["status"] == "error"
    assert result["installed"] == "v0.19.5" and result["previous"] == "v0.19.0"
    assert result["changed"] is True and result["constraint"] == "^1.0"
    assert "Nothing else was changed" not in result["message"]
    assert "composer.json" in result["message"]


def test_backend_update_keeps_its_range_requirement_via_require():
    b = backend()
    backend_pkg = "webwerkwien/contao-ai-backend-bundle"
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.3.0"), \
         patch.object(bundles, "get_installed_package_versions",
                      side_effect=[{backend_pkg: "v0.2.0"}, {backend_pkg: "v0.3.0"}]):
        result = bundles.install_bundle(b, "backend", "update")
    cmd = composer_cmd(b)
    assert "composer require" in cmd
    assert "'webwerkwien/contao-ai-backend-bundle:>=0.1 <2.0'" in cmd
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


# --- the bundle brings its own dependencies along (2026-10-10) ------------------------

BACKEND_PKG = "webwerkwien/contao-ai-backend-bundle"


def snapshot_stdout(packages: dict) -> dict:
    return {"returncode": 0, "stdout": "".join(f"{n} {v}\n" for n, v in packages.items()), "stderr": ""}


def test_update_lets_the_bundle_move_its_own_dependencies_but_not_contao():
    """c5, 2026-10-09: backend v0.11.0 needs symfony/ai ^0.14, the lock held 0.13, and a
    `require` without -w resolved to the installed v0.10.0. -w moves the bundle's own
    dependencies; -W would move root requirements -- Contao itself -- as well."""
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.11.0"), \
         patch.object(bundles, "get_installed_package_versions",
                      side_effect=[{BACKEND_PKG: "v0.10.0"}, {BACKEND_PKG: "v0.11.0"}]):
        result = bundles.install_bundle(b, "backend", "update")
    cmd = composer_cmd(b)
    assert "--update-with-dependencies" in cmd and "--minimal-changes" in cmd
    assert "--update-with-all-dependencies" not in cmd and " -W" not in cmd
    assert result["status"] == "ok"


def test_install_brings_the_dependencies_along_too():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.0.0"):
        bundles.install_bundle(b, "core", "install")
    assert "--update-with-dependencies" in composer_cmd(b)


def test_a_composer_without_minimal_changes_gets_the_update_with_dependencies_alone():
    from contao_ai_cli.utils.contao_backend import ContaoBackendError
    b = backend()
    b.run_raw.side_effect = [
        ContaoBackendError('The "--minimal-changes" option does not exist.'),
        {"returncode": 0, "stdout": "", "stderr": ""},
    ]
    bundles.composer_bundle(b, bundles.REQUIREMENTS["core"], "require")
    first, second = (c.args[0] for c in b.run_raw.call_args_list)
    assert "--minimal-changes" in first
    assert "--update-with-dependencies" in second and "--minimal-changes" not in second


def test_a_real_resolution_failure_is_not_retried_with_looser_flags():
    """The flag itself can appear in Composer's report -- only its own 'does not exist'
    wording means an old Composer."""
    import pytest
    from contao_ai_cli.utils.contao_backend import ContaoBackendError
    b = backend()
    b.run_raw.side_effect = ContaoBackendError(
        "composer failed", stderr="Running composer update x --minimal-changes\n"
                                  "Your requirements could not be resolved to an installable set of packages.")
    with pytest.raises(ContaoBackendError):
        bundles.composer_bundle(b, bundles.REQUIREMENTS["core"], "require")
    assert b.run_raw.call_count == 1


def test_the_answer_names_every_other_package_that_moved():
    b = backend()
    before = {BACKEND_PKG: "v0.10.0", "symfony/ai-platform": "v0.13.0", "symfony/ai-agent": "v0.13.0",
              "contao/core-bundle": "5.7.14", "old/removed": "1.0.0"}
    after = {BACKEND_PKG: "v0.11.0", "symfony/ai-platform": "v0.14.0", "symfony/ai-agent": "v0.14.0",
             "contao/core-bundle": "5.7.14", "new/added": "2.0.0"}
    snapshots = iter([snapshot_stdout(before), snapshot_stdout(after)])

    def run_raw(cmd, **_):
        return next(snapshots) if "installed.json" in cmd else {"returncode": 0, "stdout": "", "stderr": ""}

    b.run_raw.side_effect = run_raw
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.11.0"), \
         patch.object(bundles, "get_installed_package_versions",
                      side_effect=[{BACKEND_PKG: "v0.10.0"}, {BACKEND_PKG: "v0.11.0"}]):
        result = bundles.install_bundle(b, "backend", "update")
    assert result["dependenciesChanged"] == {
        "new/added": {"from": None, "to": "2.0.0"},
        "old/removed": {"from": "1.0.0", "to": None},
        "symfony/ai-agent": {"from": "v0.13.0", "to": "v0.14.0"},
        "symfony/ai-platform": {"from": "v0.13.0", "to": "v0.14.0"},
    }


def test_unreadable_snapshots_say_unknown_not_nothing():
    """None and {} are different answers: "could not tell" must not read as "nothing else moved"."""
    assert bundles.dependency_changes(None, {"a/b": "1"}, BACKEND_PKG) is None
    assert bundles.dependency_changes({"a/b": "1"}, None, BACKEND_PKG) is None
    assert bundles.dependency_changes({"a/b": "1"}, {"a/b": "1"}, BACKEND_PKG) == {}
    b = backend()  # run_raw answers an empty stdout: installed.json unreadable
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.0.0"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "ok" and result["dependenciesChanged"] is None


def test_a_held_back_update_names_what_moved_as_well():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.20.0"), \
         versions("v0.19.0", "v0.19.5"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["status"] == "error" and "dependenciesChanged" in result
