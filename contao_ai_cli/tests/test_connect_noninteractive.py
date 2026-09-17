"""connect runs once per site and is the only step that needed a terminal -- no more (2026-09-17)."""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli import cli_connect as mod
from contao_ai_cli.utils.contao_backend import ContaoBackendError

STATE = {"cli": {"installed": "0.21.0", "latest": "0.21.0", "up_to_date": True},
         "contao": {"installed": "5.7.13"},
         "core": {"reachable": True, "installed": None, "latest": "0.19.0", "update_available": False},
         "backend": {"installed": None, "latest": "0.3.0", "update_available": False},
         "bridge": {"state": "not_installed", "installed": False, "configured": False}}
ARGS = ["--host", "h", "--user", "u", "--root", "/r", "--name", "shop", "--json"]


def invoke(tmp_path, backend=None, args=ARGS):
    backend = backend or MagicMock(**{"run.return_value": {"stdout": "Contao 5.7.13", "stderr": "", "returncode": 0}})
    with patch.object(mod.session_mod, "DEFAULT_SESSION_DIR", str(tmp_path)), \
         patch.object(mod.session_mod, "get_session_path", side_effect=lambda n: str(tmp_path / f"{n}.json")), \
         patch.object(mod, "ContaoBackend", return_value=backend), \
         patch.object(mod, "collect_status", return_value=STATE):
        return CliRunner().invoke(mod.connect, args, obj={}, input="")


def test_no_prompt_and_one_json_answer(tmp_path):
    result = invoke(tmp_path)
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["status"] == "connected" and "backup" in out["warning"].lower()
    assert out["nextSteps"][0]["command"] == "contao-ai-cli --session shop backup create"
    assert out["state"]["contao"]["installed"] == "5.7.13"


def test_a_failed_connection_saves_nothing(tmp_path):
    backend = MagicMock(**{"run.side_effect": ContaoBackendError("refused")})
    result = invoke(tmp_path, backend)
    assert result.exit_code == 1
    assert "No session was saved" in json.loads(result.stdout)["message"]
    assert not (tmp_path / "shop.json").exists()


def test_reconnecting_keeps_the_bridge(tmp_path):
    (tmp_path / "shop.json").write_text(json.dumps(
        {"host": "old", "bridge_url": "https://shop.at", "bridge_token": "5.secret"}), encoding="utf-8")
    out = json.loads(invoke(tmp_path).stdout)
    saved = json.loads((tmp_path / "shop.json").read_text(encoding="utf-8"))
    assert out["replaced"] is True
    assert saved["host"] == "h" and saved["bridge_token"] == "5.secret"


def test_a_broken_session_file_is_repaired_not_a_crash(tmp_path):
    """Review 2026-09-17: load_session raised on an empty file, so reconnecting crashed."""
    (tmp_path / "shop.json").write_text("", encoding="utf-8")
    result = invoke(tmp_path)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["replaced"] is True
    assert json.loads((tmp_path / "shop.json").read_text(encoding="utf-8"))["host"] == "h"


def test_the_core_bundle_flag_follows_the_state(tmp_path):
    invoke(tmp_path)
    assert json.loads((tmp_path / "shop.json").read_text(encoding="utf-8"))["core_bundle_available"] is False


def test_nothing_is_installed_or_backed_up(tmp_path):
    backend = MagicMock(**{"run.return_value": {"stdout": "Contao", "stderr": "", "returncode": 0}})
    invoke(tmp_path, backend)
    assert [c.args[0] for c in backend.run.call_args_list] == ["--version"]
    backend.run_raw.assert_not_called()


def test_a_first_contact_is_reported_as_host_key_accepted(tmp_path):
    """v0.20.0 released this field as `host_key_accepted`; renaming it to
    camelCase was an undocumented break (review 2026-09-17)."""
    backend = MagicMock(**{"run.return_value": {
        "stdout": "Contao 5.7.13",
        "stderr": "Warning: Permanently added 'h' (ED25519) to the list of known hosts.",
        "returncode": 0,
    }})
    out = json.loads(invoke(tmp_path, backend).stdout)
    assert "host_key_accepted" in out and "hostKeyAccepted" not in out
    assert "h" in out["host_key_accepted"]
