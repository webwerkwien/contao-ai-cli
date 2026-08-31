"""
The self-update check asks the same source the installer installs from.

`install_cli_update()` runs `pipx install git+…@v<x>`, so a **tag** is what
"available" means. The check asked `releases/latest` instead — a different
source — and on 2026-08-31 the two were found three versions apart: releases
stopped at v0.5.2 while tags carried on to v0.8.0.

Nothing looked wrong. `is_newer_version("0.5.2", "0.8.0")` is False, so the
answer was "up to date" — correct words, dead mechanism. A genuine update would
have gone unmentioned in exactly the same way, which is the same shape as the
v0.4.3 bug where `pipx upgrade` reported success for a no-op.

These tests pin the two properties that keep it honest: the highest version
wins regardless of the order the API returns, and anything that is not a plain
release version is ignored.
"""
import json
from unittest.mock import MagicMock, patch

from contao_ai_cli.cli import helpers


def with_tags(names):
    """Patch the tags endpoint to answer with these tag names."""
    payload = json.dumps([{"name": n} for n in names]).encode()
    resp = MagicMock()
    resp.read.return_value = payload
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda *a: False
    return patch("urllib.request.urlopen", return_value=resp)


class TestLatestReleasedTag:
    def test_the_highest_version_wins_not_the_first_entry(self):
        """The tags endpoint promises no ordering; relying on position would
        make the answer depend on something nobody controls."""
        with with_tags(["v0.5.2", "v0.8.0", "v0.7.0", "v0.6.0"]):
            assert helpers.latest_released_tag() == "0.8.0"

    def test_two_digit_segments_compare_numerically(self):
        """String order puts v0.2.9 above v0.2.13 — the trap fixed in v0.5.2."""
        with with_tags(["v0.2.9", "v0.2.13"]):
            assert helpers.latest_released_tag() == "0.2.13"

    def test_the_leading_v_is_dropped(self):
        with with_tags(["v0.8.0"]):
            assert helpers.latest_released_tag() == "0.8.0"

    def test_non_release_tags_are_ignored(self):
        with with_tags(["dev-main", "1.0.0-beta", "nightly", "v0.7.0"]):
            assert helpers.latest_released_tag() == "0.7.0"

    def test_nothing_usable_yields_none_rather_than_a_guess(self):
        with with_tags(["dev-main", "nightly"]):
            assert helpers.latest_released_tag() is None

    def test_an_empty_repository_yields_none(self):
        with with_tags([]):
            assert helpers.latest_released_tag() is None

    def test_a_network_failure_is_silence_not_a_crash(self):
        with patch("urllib.request.urlopen", side_effect=OSError("no network")):
            assert helpers.latest_released_tag() is None


class TestCheckCliUpdate:
    def test_a_newer_tag_is_reported(self):
        with patch.object(helpers, "latest_released_tag", return_value="9.9.9"):
            result = helpers.check_cli_update()
        assert result["update_available"] is True
        assert result["latest"] == "9.9.9"

    def test_the_current_version_is_not_an_update(self):
        with patch.object(helpers, "latest_released_tag", return_value=helpers.__version__):
            assert helpers.check_cli_update()["update_available"] is False

    def test_an_older_tag_is_not_an_update(self):
        """The arrow pointed backwards once already, in v0.5.2."""
        with patch.object(helpers, "latest_released_tag", return_value="0.0.1"):
            assert helpers.check_cli_update()["update_available"] is False

    def test_an_unreachable_api_says_nothing_rather_than_something_wrong(self):
        with patch.object(helpers, "latest_released_tag", return_value=None):
            result = helpers.check_cli_update()
        assert result["latest"] is None
        assert result["update_available"] is False
        assert result["current"] == helpers.__version__
