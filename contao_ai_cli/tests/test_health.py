"""
Tests for the health command's bridge reporting.

Until v0.5.1 the bridge line said "not configured" whether contao-ai-backend-bundle
was missing from the server or merely present without a token. The two need
opposite next steps — install the package, or set a token — so an agent reading
"not configured" would go set a token into nothing.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_health import _bridge_state, health
from contao_ai_cli.cli.helpers import (
    BACKEND_BUNDLE, CORE_BUNDLE, get_installed_package_versions,
    is_newer_version, version_tuple,
)


class TestBridgeState:
    def test_installed_and_configured_is_ready(self):
        assert _bridge_state(True, True) == "ready"

    def test_installed_without_token_is_not_configured(self):
        assert _bridge_state(True, False) == "not_configured"

    def test_missing_bundle_is_not_installed(self):
        assert _bridge_state(False, False) == "not_installed"

    def test_missing_bundle_outranks_a_configured_session(self):
        """A token pointing at a server with no bundle is broken, not ready."""
        assert _bridge_state(False, True) == "not_installed"

    def test_unreachable_server_without_token_is_unknown(self):
        """None means 'could not look', which is not the same as 'not installed'."""
        assert _bridge_state(None, False) == "unknown"

    def test_unreachable_server_with_token_still_reports_ready(self):
        """The session is configured; we simply could not verify the far end."""
        assert _bridge_state(None, True) == "ready"


class TestInstalledPackageVersions:
    def make_backend(self, stdout=""):
        backend = MagicMock()
        backend.php_path = "php"
        backend.run_raw.return_value = {"returncode": 0, "stdout": stdout, "stderr": ""}
        return backend

    def test_reads_both_bundles_in_one_call(self):
        backend = self.make_backend(
            f"{CORE_BUNDLE} v0.2.13\n{BACKEND_BUNDLE} v0.1.4\n"
        )
        result = get_installed_package_versions(backend, [CORE_BUNDLE, BACKEND_BUNDLE])

        assert result == {CORE_BUNDLE: "v0.2.13", BACKEND_BUNDLE: "v0.1.4"}
        assert backend.run_raw.call_count == 1

    def test_absent_package_is_none(self):
        backend = self.make_backend(f"{CORE_BUNDLE} v0.2.13\n")
        result = get_installed_package_versions(backend, [CORE_BUNDLE, BACKEND_BUNDLE])

        assert result[BACKEND_BUNDLE] is None

    def test_ssh_failure_yields_none_for_everything(self):
        backend = MagicMock()
        backend.php_path = "php"
        backend.run_raw.side_effect = RuntimeError("connection refused")

        result = get_installed_package_versions(backend, [CORE_BUNDLE, BACKEND_BUNDLE])

        assert result == {CORE_BUNDLE: None, BACKEND_BUNDLE: None}


def run_health(tmp_path, session, installed_versions):
    """Run `health --json` against a fake session and a fake installed.json."""
    session_path = tmp_path / "s.json"
    session_path.write_text(json.dumps(session), encoding="utf-8")

    with patch("contao_ai_cli.cli.cli_health.ContaoBackend.from_session",
               return_value=MagicMock(php_path="php")), \
         patch("contao_ai_cli.cli.cli_health.get_installed_package_versions",
               return_value=installed_versions), \
         patch("contao_ai_cli.cli.cli_health.get_core_bundle_latest_version",
               return_value="0.2.13"), \
         patch("contao_ai_cli.cli.cli_health.check_cli_update",
               return_value={"current": "0.5.1", "latest": "0.5.1",
                             "update_available": False}):
        result = CliRunner().invoke(
            health, obj={"as_json": True, "session": str(session_path)}
        )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


BASE_SESSION = {"host": "example.com", "user": "deploy", "contao_root": "/web"}


class TestHealthOutput:
    def test_reports_not_installed_when_the_bundle_is_absent(self, tmp_path):
        out = run_health(tmp_path, BASE_SESSION,
                         {CORE_BUNDLE: "v0.2.13", BACKEND_BUNDLE: None})

        assert out["bridge"]["state"] == "not_installed"
        assert out["bridge"]["installed"] is False
        assert out["bridge"]["configured"] is False

    def test_reports_not_configured_when_the_bundle_is_there(self, tmp_path):
        out = run_health(tmp_path, BASE_SESSION,
                         {CORE_BUNDLE: "v0.2.13", BACKEND_BUNDLE: "v0.1.4"})

        assert out["bridge"]["state"] == "not_configured"
        assert out["bridge"]["installed"] is True

    def test_reports_ready_and_masks_the_token(self, tmp_path):
        session = dict(BASE_SESSION, bridge_url="https://example.com",
                       bridge_token="5.deadbeefdeadbeefdeadbeefdeadbeef")
        out = run_health(tmp_path, session,
                         {CORE_BUNDLE: "v0.2.13", BACKEND_BUNDLE: "v0.1.4"})

        assert out["bridge"]["state"] == "ready"
        assert out["bridge"]["url"] == "https://example.com"
        assert "deadbeefdeadbeefdeadbeefdeadbeef" not in out["bridge"]["token"]

    def test_the_two_states_are_distinguishable_in_text_output(self, tmp_path):
        """The regression itself: both cases printed the same line."""
        session_path = tmp_path / "s.json"
        session_path.write_text(json.dumps(BASE_SESSION), encoding="utf-8")

        lines = {}
        for label, versions in (
            ("absent",  {CORE_BUNDLE: "v0.2.13", BACKEND_BUNDLE: None}),
            ("present", {CORE_BUNDLE: "v0.2.13", BACKEND_BUNDLE: "v0.1.4"}),
        ):
            with patch("contao_ai_cli.cli.cli_health.ContaoBackend.from_session",
                       return_value=MagicMock(php_path="php")), \
                 patch("contao_ai_cli.cli.cli_health.get_installed_package_versions",
                       return_value=versions), \
                 patch("contao_ai_cli.cli.cli_health.get_core_bundle_latest_version",
                       return_value="0.2.13"), \
                 patch("contao_ai_cli.cli.cli_health.check_cli_update",
                       return_value={"current": "0.5.1", "latest": "0.5.1",
                                     "update_available": False}):
                result = CliRunner().invoke(
                    health, obj={"as_json": False, "session": str(session_path)}
                )
            assert result.exit_code == 0, result.output
            lines[label] = [l for l in result.output.splitlines() if "Bridge" in l][0]

        assert lines["absent"] != lines["present"]
        assert "not installed" in lines["absent"]
        assert "not configured" in lines["present"]


class TestVersionComparison:
    """
    Regression: `latest != current` called every unreleased working copy behind.
    Running v0.5.1 locally, health said "-> update available: v0.5.0".
    """

    def test_a_newer_release_is_an_update(self):
        assert is_newer_version("0.5.2", "0.5.1") is True
        assert is_newer_version("v0.6.0", "0.5.9") is True
        assert is_newer_version("1.0.0", "0.99.99") is True

    def test_an_older_release_is_not_an_update(self):
        assert is_newer_version("0.5.0", "0.5.1") is False
        assert is_newer_version("0.2.13", "0.3.0") is False

    def test_the_same_release_is_not_an_update(self):
        assert is_newer_version("0.5.1", "0.5.1") is False
        assert is_newer_version("v0.5.1", "0.5.1") is False

    def test_differing_precision_compares_by_value(self):
        assert is_newer_version("0.5", "0.5.0") is False
        assert is_newer_version("0.5.0", "0.5") is False
        assert is_newer_version("0.5.1", "0.5") is True

    def test_numeric_not_lexicographic(self):
        """'0.2.9' > '0.2.13' as strings, and that is the whole point."""
        assert is_newer_version("0.2.13", "0.2.9") is True
        assert is_newer_version("0.2.9", "0.2.13") is False

    def test_unparsable_versions_stay_silent(self):
        """A wrong arrow is worse than no arrow."""
        assert is_newer_version("dev-main", "0.5.1") is False
        assert is_newer_version("0.5.2", "dev-main") is False
        assert is_newer_version("1.0.0-beta", "0.9.0") is False
        assert is_newer_version(None, "0.5.1") is False
        assert is_newer_version("", "0.5.1") is False

    def test_version_tuple_rejects_non_releases(self):
        assert version_tuple("v1.2.3") == (1, 2, 3)
        assert version_tuple("dev-main") == ()
        assert version_tuple("") == ()
        assert version_tuple(None) == ()
