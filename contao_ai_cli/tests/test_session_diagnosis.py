"""
What the CLI says when it cannot find the session, as opposed to the bundle.

`_require_core_bundle` used to answer every failure with the same sentence:

    'page read' requires contao-ai-core-bundle which is not installed on this
    server. Install with: composer require webwerkwien/contao-ai-core-bundle

For a mistyped session name that is a wrong answer that looks like an answer.
There is no server, nothing was asked of one, and the advice points at a
composer command for an installation that does not exist. Found on 2026-09-01
by typing `--session c5` instead of `--session c5-axeltest`.

The three causes are separate questions with separate answers, so the tests
below pin them apart rather than checking that "some error" is raised.
"""
import json

import click
import pytest

from contao_ai_cli.cli import helpers
from contao_ai_cli.core import session as session_mod


class _Ctx:
    """Just enough of a click context for the helper."""

    def __init__(self, session):
        self.obj = {"session": session}


@pytest.fixture
def session_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DEFAULT_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(session_mod, "DEFAULT_SESSION_FILE", str(tmp_path / "session.json"))
    return tmp_path


def _write_session(session_dir, name: str, **fields):
    path = session_dir / f"{name}.json"
    cfg = {"host": "example.org", "user": "u", "contao_root": "/web"}
    cfg.update(fields)
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return str(path)


def test_unknown_session_does_not_blame_the_bundle(session_dir):
    _write_session(session_dir, "c5-axeltest", core_bundle_available=True)
    missing = str(session_dir / "c5.json")

    with pytest.raises(click.UsageError) as excinfo:
        helpers._require_core_bundle(_Ctx(missing), "page read")

    message = str(excinfo.value)
    assert "not installed" not in message
    assert "composer require" not in message


def test_unknown_session_names_the_session_and_lists_the_real_ones(session_dir):
    _write_session(session_dir, "c5-axeltest", core_bundle_available=True)
    _write_session(session_dir, "wienerwandern", core_bundle_available=True)

    with pytest.raises(click.UsageError) as excinfo:
        helpers._require_core_bundle(_Ctx(str(session_dir / "c5.json")), "page read")

    message = str(excinfo.value)
    # The name the caller typed, so they can see the typo.
    assert "c5" in message
    # And what they could have meant. A dead end that knows the answer and
    # keeps it is the same failure in a smaller form.
    assert "c5-axeltest" in message
    assert "wienerwandern" in message


def test_no_sessions_at_all_points_at_connect(session_dir):
    with pytest.raises(click.UsageError) as excinfo:
        helpers._require_core_bundle(_Ctx(str(session_dir / "c5.json")), "page read")

    assert "connect" in str(excinfo.value)


def test_unreadable_session_file_says_so(session_dir):
    broken = session_dir / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")

    with pytest.raises(click.UsageError) as excinfo:
        helpers._require_core_bundle(_Ctx(str(broken)), "page read")

    message = str(excinfo.value)
    assert "not installed" not in message
    assert "broken.json" in message


def test_session_without_the_bundle_still_gets_the_install_hint(session_dir):
    path = _write_session(session_dir, "plain", core_bundle_available=False)

    with pytest.raises(click.UsageError) as excinfo:
        helpers._require_core_bundle(_Ctx(path), "page read")

    message = str(excinfo.value)
    assert "not installed" in message
    assert "composer require" in message


def test_session_with_the_bundle_passes(session_dir):
    path = _write_session(session_dir, "ok", core_bundle_available=True)

    helpers._require_core_bundle(_Ctx(path), "page read")


def test_legacy_bridge_available_key_still_passes(session_dir):
    """Sessions written before v0.5.0 carry the old key name."""
    path = _write_session(session_dir, "old", bridge_available=True)

    helpers._require_core_bundle(_Ctx(path), "page read")
