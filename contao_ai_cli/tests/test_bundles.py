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
    """On a live installation: v0.21.1 required `^0.20.0` and so
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
    """Composer exits 0 with an older version when e.g. the
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
    """Every helper below this swallows ContaoBackendError, so
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


# --- the bundle brings its own dependencies along -------------------------------------

BACKEND_PKG = "webwerkwien/contao-ai-backend-bundle"


def snapshot_stdout(packages: dict) -> dict:
    return {"returncode": 0, "stdout": "".join(f"{n} {v}\n" for n, v in packages.items()), "stderr": ""}


def test_update_lets_the_bundle_move_its_own_dependencies_but_not_contao():
    """Backend v0.11.0 needs symfony/ai ^0.14, the lock held 0.13, and a
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


def test_start_up_warnings_on_stdout_are_not_packages():
    """Two identical warning sets read as {} -- "nothing else
    moved" -- where the truth is "unknown"."""
    b = backend()
    b.run_raw.return_value = {"returncode": 0, "stderr": "", "stdout":
                              "PHP Warning:  PHP Startup: Unable to load dynamic library 'imagick.so'\n"
                              "Warning: foreach() argument must be of type array|object\n"}
    assert bundles.installed_snapshot(b) is None
    b.run_raw.return_value = snapshot_stdout({"contao/core-bundle": "5.7.14"}) | {
        "stdout": "PHP Warning:  imagick\ncontao/core-bundle 5.7.14\n"}
    assert bundles.installed_snapshot(b) == {"contao/core-bundle": "5.7.14"}


def test_a_package_name_with_capitals_is_still_a_package():
    """installed.json keeps the pretty name; Composer 1 allowed capitals.
    Dropped from both snapshots, such a package would vanish from the diff silently."""
    b = backend()
    b.run_raw.return_value = snapshot_stdout({"Legacy/Old-Bundle": "1.0.0", "contao/core-bundle": "5.7.14"})
    assert bundles.installed_snapshot(b) == {"Legacy/Old-Bundle": "1.0.0", "contao/core-bundle": "5.7.14"}


def test_the_retry_reads_the_error_as_run_raw_builds_it():
    """run_raw puts an excerpt into the message and the whole stderr into .stderr."""
    from contao_ai_cli.utils.contao_backend import ContaoBackendError
    b = backend()
    b.run_raw.side_effect = [
        ContaoBackendError("Shell command failed (exit 1). Stderr: cut",
                           stderr='\n  The "--minimal-changes" option does not exist.  \n'),
        {"returncode": 0, "stdout": "", "stderr": ""},
    ]
    bundles.composer_bundle(b, bundles.REQUIREMENTS["core"], "require")
    assert b.run_raw.call_count == 2


def test_a_timeout_is_not_retried():
    import pytest
    from contao_ai_cli.utils.contao_backend import ContaoBackendError
    b = backend()
    b.run_raw.side_effect = ContaoBackendError("Shell command timed out after 600 s")
    with pytest.raises(ContaoBackendError):
        bundles.composer_bundle(b, bundles.REQUIREMENTS["core"], "require")
    assert b.run_raw.call_count == 1


def test_a_bundle_missing_afterwards_says_what_moved_instead():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, None):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error" and "dependenciesChanged" in result


def test_a_held_back_update_names_what_moved_as_well():
    b = backend()
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), \
         patch.object(bundles, "get_bundle_latest_version", return_value="0.20.0"), \
         versions("v0.19.0", "v0.19.5"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["status"] == "error" and "dependenciesChanged" in result


# --- contao:migrate after Composer (v1.7.0) -----------------------------------------------

MIGRATE_OUTPUT = "\n".join([
    '{"type":"backup-result","createdAt":"2026-10-13T16:00:00+00:00","size":1234,"name":"backup__20261013160000.sql.gz"}',
    '{"type":"migration-pending","names":["Add the contao-ai user"],"hash":"x"}',
    '{"type":"migration-result","message":"Added the contao-ai user","isSuccessful":true}',
    '{"type":"schema-pending","commands":["ALTER TABLE tl_user ADD ai_model VARCHAR(64)"]}',
    '{"type":"schema-execute","command":"ALTER TABLE tl_user ADD ai_model VARCHAR(64)"}',
    '{"type":"schema-result","command":"ALTER TABLE tl_user ADD ai_model VARCHAR(64)","isSuccessful":true}',
    '{"type":"schema-result","command":"ALTER TABLE tl_user ADD ai_x INT","isSuccessful":false,"message":"retried"}',
])


def migrating_backend(migrate_stdout="", migrate_error=None, returncode=0, stderr=""):
    """run_raw answers the migrate call with its own output; everything else as before."""
    b = backend()

    def run_raw(command, timeout=None, **kwargs):
        if "contao:migrate" in command:
            if migrate_error:
                raise migrate_error
            return {"returncode": returncode, "stdout": migrate_stdout, "stderr": stderr}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    b.run_raw.side_effect = run_raw
    return b


def migrate_calls(b):
    return [c for c in b.run_raw.call_args_list if "contao:migrate" in c.args[0]]


def test_an_install_runs_the_migrations_after_composer_and_reports_them():
    b = migrating_backend(MIGRATE_OUTPUT)
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.7.2"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "ok"
    assert result["migrate"] == {"migrations": 1, "schemaChanges": 1, "backup": "backup__20261013160000.sql.gz"}
    commands = [c.args[0] for c in b.run_raw.call_args_list]
    composer_at = next(i for i, c in enumerate(commands) if " composer " in f" {c} ")
    migrate_at = next(i for i, c in enumerate(commands) if "contao:migrate" in c)
    assert composer_at < migrate_at
    call = migrate_calls(b)[0]
    assert "--no-interaction" in call.args[0] and "--format=ndjson" in call.args[0]
    assert "--with-deletes" not in call.args[0] and "--no-backup" not in call.args[0]
    assert call.kwargs["timeout"] == bundles.MIGRATE_TIMEOUT


def test_an_update_runs_them_too_and_nothing_to_do_is_zero():
    b = migrating_backend("")
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions("v1.7.1", "v1.7.2"), \
         patch.object(bundles, "get_bundle_latest_version", return_value="1.7.2"):
        result = bundles.install_bundle(b, "core", "update")
    assert result["status"] == "ok"
    assert result["migrate"] == {"migrations": 0, "schemaChanges": 0, "backup": None}
    assert len(migrate_calls(b)) == 1


def test_no_composer_run_means_no_migration():
    b = migrating_backend(MIGRATE_OUTPUT)
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions("v1.7.2"):
        bundles.install_bundle(b, "core", "install")
    assert migrate_calls(b) == []


def test_a_failed_migration_keeps_the_install_but_is_an_error():
    from contao_ai_cli.utils.contao_backend import ContaoBackendError

    b = migrating_backend(migrate_error=ContaoBackendError("Shell command failed (exit 1). Stderr: Access denied"))
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.7.2"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error" and result["code"] == 1
    assert result["installed"] == "v1.7.2"
    assert "contao:migrate failed" in result["message"] and "Access denied" in result["message"]
    assert "contao-ai-cli contao migrate" in result["message"]


def test_an_error_reported_by_contao_with_exit_1_keeps_its_reason_and_the_dump():
    """Contao emits error/problem only with exit 1 (MigrateCommand); the reason is on stdout."""
    out = MIGRATE_OUTPUT + '\n{"type":"error","message":"Table tl_user is locked"}'
    b = migrating_backend(out, returncode=1)
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.7.2"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error"
    assert "Table tl_user is locked" in result["message"]
    assert "backup__20261013160000.sql.gz" in result["message"]
    assert migrate_calls(b)[0].kwargs["check"] is False


def test_a_failed_migration_with_exit_0_is_an_error():
    """Contao carries on after a migration with isSuccessful false and exits 0."""
    out = '{"type":"migration-result","message":"Could not add the user","isSuccessful":false}'
    b = migrating_backend(out)
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.7.2"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error"
    assert "migration failed: Could not add the user" in result["message"]


def test_a_restart_on_an_unexpected_pending_migration_is_no_error():
    out = "\n".join([
        '{"type":"migration-result","message":"Expected \\"A\\" got \\"B\\".","isSuccessful":false}',
        '{"type":"migration-result","message":"Ran B","isSuccessful":true}',
        '{"type":"warning","message":"Running MySQL in non-strict mode can cause corrupt data."}',
    ])
    b = migrating_backend(out)
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.7.2"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "ok"
    assert result["migrate"]["migrations"] == 1
    assert result["migrate"]["warnings"] == ["Running MySQL in non-strict mode can cause corrupt data."]


def test_a_schema_change_that_fails_for_good_names_its_reason():
    """Contao exits 1 without an error event; the reason is in schema-result.
    A statement that failed once and then went through is no error."""
    out = "\n".join([
        '{"type":"schema-result","command":"ALTER TABLE tl_a ADD x INT","isSuccessful":false,"message":"retry"}',
        '{"type":"schema-result","command":"ALTER TABLE tl_a ADD x INT","isSuccessful":true}',
        '{"type":"schema-result","command":"ALTER TABLE tl_user ADD y TEXT","isSuccessful":false,"message":"Row size too large"}',
    ])
    b = migrating_backend(out, returncode=1)
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.7.2"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error"
    assert "schema change failed: ALTER TABLE tl_user ADD y TEXT: Row size too large" in result["message"]
    assert "tl_a" not in result["message"]
    assert result["migrate"]["schemaChanges"] == 1


def test_a_failed_exit_without_any_event_names_stderr():
    b = migrating_backend("", returncode=255, stderr="PHP Fatal error: Allowed memory size exhausted")
    with patch.object(bundles, "detect_contao_manager", return_value=MANAGED), versions(None, "v1.7.2"):
        result = bundles.install_bundle(b, "core", "install")
    assert result["status"] == "error" and "exit 255" in result["message"]
    assert "Allowed memory size" in result["message"]


def test_installing_the_backend_names_the_optional_bridge_until_it_is_configured(tmp_path):
    """v1.8.0: the token half of the bridge was nowhere to be read."""
    import json as _json
    from click.testing import CliRunner
    from contao_ai_cli.cli import cli_bundle

    done = {"status": "ok", "installed": "v0.16.3", "changed": True}
    for cfg, expected in (({"host": "h"}, 1), ({"host": "h", "bridge_url": "https://x", "bridge_token": "5.t"}, 0)):
        session = tmp_path / "shop.json"
        session.write_text(_json.dumps(cfg), encoding="utf-8")
        with patch.object(cli_bundle, "_get_backend", return_value=MagicMock()), \
             patch.object(cli_bundle.bundles_mod, "install_bundle", return_value=dict(done)):
            out = CliRunner().invoke(cli_bundle.bundle, ["install", "backend", "--json"], obj={"session": str(session)})
        steps = _json.loads(out.output).get("nextSteps", [])
        assert len(steps) == expected, cfg
        if steps:
            assert steps[0]["optional"] is True and "--token-stdin" in steps[0]["command"]
            # v1.8.0: without --session the token would land in the default session.
            assert steps[0]["command"].startswith(f"contao-ai-cli --session {session} bridge configure")

    # A failed install suggests nothing for a bundle that is not there.
    session.write_text(_json.dumps({"host": "h"}), encoding="utf-8")
    failed = {"status": "error", "code": 1, "message": "Composer failed"}
    with patch.object(cli_bundle, "_get_backend", return_value=MagicMock()), \
         patch.object(cli_bundle.bundles_mod, "install_bundle", return_value=failed):
        out = CliRunner().invoke(cli_bundle.bundle, ["install", "backend", "--json"], obj={"session": str(session)})
    assert "nextSteps" not in _json.loads(out.output)


def test_the_core_flag_is_set_when_installed_even_if_the_migration_failed(tmp_path):
    """The flag stayed false and every core command answered "not installed"."""
    import json as _json
    from click.testing import CliRunner
    from contao_ai_cli.cli import cli_bundle

    session = tmp_path / "s.json"
    session.write_text(_json.dumps({"host": "h", "core_bundle_available": False}), encoding="utf-8")
    failed = {"status": "error", "code": 1, "installed": "v1.7.2", "message": "migrate failed"}
    with patch.object(cli_bundle, "_get_backend", return_value=MagicMock()), \
         patch.object(cli_bundle.bundles_mod, "install_bundle", return_value=failed):
        result = CliRunner().invoke(cli_bundle.bundle, ["install", "core", "--json"], obj={"session": str(session)})
    assert result.exit_code == 1
    assert _json.loads(session.read_text(encoding="utf-8"))["core_bundle_available"] is True
