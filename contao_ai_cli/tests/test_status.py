"""The state `health` reports, and the steps `connect` derives from it."""
from unittest.mock import patch

from contao_ai_cli.core.status import WARNING, collect_status, next_steps


def state(cli_up=True, core=None, core_update=False, backend=None, bridge="not_installed"):
    return {
        "cli": {"installed": "0.21.0", "latest": "0.21.0" if cli_up else "0.22.0", "up_to_date": cli_up},
        "contao": {"installed": "5.7.13"},
        "core": {"reachable": True, "installed": core, "latest": "0.19.0",
                 "update_available": core_update, "up_to_date": core is not None and not core_update},
        "backend": {"installed": backend, "latest": "0.3.0", "update_available": False},
        "bridge": {"state": bridge, "installed": backend is not None, "configured": bridge == "ready"},
    }


def commands(steps):
    return [s["command"] for s in steps]


def test_a_fresh_site_starts_with_a_backup_then_the_core_bundle():
    steps = next_steps(state(core=None), "shop")
    assert commands(steps)[:2] == [
        "contao-ai-cli --session shop backup create",
        "contao-ai-cli --session shop bundle install core",
    ]


def test_an_outdated_core_bundle_is_an_update_not_an_install():
    assert "contao-ai-cli --session shop bundle update core" in commands(
        next_steps(state(core="0.18.0", core_update=True), "shop"))


def test_a_newer_cli_adds_self_update_without_a_session():
    assert "contao-ai-cli self-update" in commands(next_steps(state(cli_up=False, core="0.19.0"), "shop"))


def test_the_backend_bundle_is_offered_as_optional():
    step = [s for s in next_steps(state(core="0.19.0"), "shop") if "bundle install backend" in s["command"]][0]
    assert step["optional"] is True
    assert "bulk" in step["reason"]


def test_an_installed_backend_without_token_asks_for_bridge_configure():
    steps = next_steps(state(core="0.19.0", backend="0.3.0", bridge="not_configured"), "shop")
    assert any("bridge configure" in c for c in commands(steps))
    assert not any("bundle install backend" in c for c in commands(steps))


def test_the_default_session_needs_no_session_option():
    assert commands(next_steps(state(core=None), None))[0] == "contao-ai-cli backup create"


def test_every_step_has_a_reason():
    for step in next_steps(state(cli_up=False, core=None), "shop"):
        assert step["reason"]


def test_the_warning_names_backups():
    assert "backup" in WARNING.lower()


def test_collect_status_survives_a_missing_session(tmp_path):
    with patch("contao_ai_cli.core.status.check_cli_update",
               return_value={"current": "0.21.0", "latest": None, "update_available": False}):
        result = collect_status(str(tmp_path / "none.json"))
    assert result["core"]["reachable"] is False
    assert result["contao"] == {"installed": None}
    assert result["bridge"]["state"] == "unknown"
