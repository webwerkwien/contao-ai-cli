"""
`health` must name the Contao it is sitting on.

Until now it reported our three parts — CLI, core bundle, bridge — and said
nothing about the Contao underneath, although the SSH session can read it from
composer.lock at any time. During the advisory round of 2026-08-25 (eleven
advisories, patched in 5.3.50 / 5.7.12) the question "is any of our sessions on
a vulnerable Contao?" therefore had to be answered by logging in past `health`
and reading the file by hand. That is precisely the question the command exists
to answer, and a site where an AI agent *writes* is the last place an outdated
Contao should sit unnoticed.

No traffic light: judging "current" needs a maintained minimum per branch, and
guessing one would be worse than saying nothing. The version alone is the answer.
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_health import health
from contao_ai_cli.cli.helpers import BACKEND_BUNDLE, CONTAO_CORE_BUNDLE, CORE_BUNDLE

BASE_SESSION = {"host": "example.com", "user": "deploy", "contao_root": "/web"}


def run_health(tmp_path, installed_versions, as_json=True):
    session_path = tmp_path / "s.json"
    session_path.write_text(json.dumps(BASE_SESSION), encoding="utf-8")

    with patch("contao_ai_cli.cli.cli_health.ContaoBackend.from_session",
               return_value=MagicMock(php_path="php")), \
         patch("contao_ai_cli.cli.cli_health.get_installed_package_versions",
               return_value=installed_versions) as versions, \
         patch("contao_ai_cli.cli.cli_health.get_core_bundle_latest_version",
               return_value="0.2.14"), \
         patch("contao_ai_cli.cli.cli_health.check_cli_update",
               return_value={"current": "0.5.2", "latest": "0.5.2",
                             "update_available": False}):
        result = CliRunner().invoke(
            health, obj={"as_json": as_json, "session": str(session_path)}
        )

    assert result.exit_code == 0, result.output
    return result, versions


def all_present(contao="5.7.11"):
    return {CORE_BUNDLE: "0.2.14", BACKEND_BUNDLE: "0.7.0", CONTAO_CORE_BUNDLE: contao}


class TestContaoVersionInHealth:
    def test_it_is_asked_for_in_the_same_round_trip(self, tmp_path):
        """The call for the bundle versions already goes there — no second one."""
        _, versions = run_health(tmp_path, all_present())

        requested = versions.call_args[0][1]
        assert CONTAO_CORE_BUNDLE in requested
        assert versions.call_count == 1

    def test_the_version_appears_in_the_json(self, tmp_path):
        result, _ = run_health(tmp_path, all_present("5.7.11"))

        payload = json.loads(result.output)
        assert payload["contao"]["installed"] == "5.7.11"

    def test_an_unreadable_version_is_reported_as_unknown_not_omitted(self, tmp_path):
        """A missing key would read as 'no Contao', which is never the case."""
        result, _ = run_health(tmp_path, all_present(contao=None))

        payload = json.loads(result.output)
        assert "contao" in payload
        assert payload["contao"]["installed"] is None

    def test_no_traffic_light_is_invented(self, tmp_path):
        result, _ = run_health(tmp_path, all_present())

        payload = json.loads(result.output)
        assert "up_to_date" not in payload["contao"]
        assert "update_available" not in payload["contao"]

    def test_the_text_output_shows_it_too(self, tmp_path):
        result, _ = run_health(tmp_path, all_present("5.7.11"), as_json=False)

        assert "5.7.11" in result.output
        assert "Contao" in result.output
