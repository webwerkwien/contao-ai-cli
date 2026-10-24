"""connect runs once per site and is the only step that needed a terminal -- no more."""
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


def test_a_root_rewritten_by_git_bash_is_named_on_failure(tmp_path):
    """Git Bash turned `--root /var/www/...` into `C:/Program Files/Git/var/www/...`."""
    backend = MagicMock(**{"run.side_effect": ContaoBackendError("cd: No such file or directory")})
    for root in ("C:/Program Files/Git/var/www/web", "C:/Git/home/site", "D:/Tools/PortableGit/srv/contao",
                 "C:\\Program Files\\Git\\var\\www\\web"):
        args = ["--host", "h", "--user", "u", "--root", root, "--json"]
        assert "MSYS_NO_PATHCONV=1" in json.loads(invoke(tmp_path, backend, args).stdout)["message"], root


def test_any_folder_behind_the_git_directory_gets_the_hint(tmp_path):
    """`--root /web` arrived as `C:/Program Files/Git/web`, no slash behind it, and
    hosts use html/, htdocs/, public_html/."""
    backend = MagicMock(**{"run.side_effect": ContaoBackendError("cd: No such file or directory")})
    with patch("contao_ai_cli.cli.cli_connect._local_git_roots", return_value=[]):
        for root in ("C:/Program Files/Git/web", "C:/Program Files/Git/html", "C:/Program Files/Git/htdocs",
                     "C:/Program Files (x86)/Git/home/u/public_html", "C:/Users/u/scoop/apps/git/current/httpdocs"):
            args = ["--host", "h", "--user", "u", "--root", root, "--json"]
            assert "MSYS_NO_PATHCONV=1" in json.loads(invoke(tmp_path, backend, args).stdout)["message"], root


def test_git_installed_elsewhere_is_found_on_this_machine(tmp_path):
    backend = MagicMock(**{"run.side_effect": ContaoBackendError("cd: No such file or directory")})
    with patch("contao_ai_cli.cli.cli_connect._local_git_roots", return_value=["E:/Tools/Git"]):
        # Windows paths are case-insensitive; MSYS writes the drive as it likes.
        for root in ("E:/Tools/Git/html", "e:/tools/git/html"):
            out = json.loads(invoke(tmp_path, backend, ["--host", "h", "--user", "u", "--root", root, "--json"]).stdout)
            assert "MSYS_NO_PATHCONV=1" in out["message"], root


def test_on_linux_and_macos_a_failed_root_gets_no_git_bash_hint(tmp_path, monkeypatch):
    """git in /usr/bin made "/" the Git root, and every --root matched."""
    from contao_ai_cli.cli import cli_connect
    monkeypatch.delenv("EXEPATH", raising=False)
    monkeypatch.setattr(cli_connect.shutil, "which", lambda name: "/usr/bin/git")
    monkeypatch.setattr(cli_connect, "Path", _PosixTree)
    assert cli_connect._local_git_roots() == []
    backend = MagicMock(**{"run.side_effect": ContaoBackendError("cd: No such file or directory")})
    out = json.loads(invoke(tmp_path, backend, ["--host", "h", "--user", "u", "--root", "/var/www/typo", "--json"]).stdout)
    assert "MSYS" not in out["message"]


class _PosixTree(__import__("pathlib").PurePosixPath):
    """A Linux file system where /usr/bin exists, on any machine running the suite."""

    def is_dir(self):
        return str(self) in ("/", "/usr", "/usr/bin")


def test_the_local_git_root_is_the_parent_with_usr_bin(tmp_path, monkeypatch):
    git = tmp_path / "Git"
    (git / "usr" / "bin").mkdir(parents=True)
    (git / "mingw64" / "bin").mkdir(parents=True)
    (git / "bin").mkdir()
    exe = git / "mingw64" / "bin" / "git.exe"
    exe.write_text("")
    from contao_ai_cli.cli import cli_connect
    monkeypatch.setenv("EXEPATH", str(git / "bin"))
    monkeypatch.setattr(cli_connect.shutil, "which", lambda name: str(exe))
    expected = str(git).replace("\\", "/")
    assert cli_connect._local_git_roots() == [expected, expected]


def test_a_real_windows_root_gets_no_git_bash_hint(tmp_path):
    backend = MagicMock(**{"run.side_effect": ContaoBackendError("refused")})
    with patch("contao_ai_cli.cli.cli_connect._local_git_roots", return_value=[]):
        for root in ("C:/inetpub/contao", "/var/www/web", "D:/Projects/Git/site", "C:/Program Files/GitHub/x"):
            args = ["--host", "h", "--user", "u", "--root", root, "--json"]
            assert "MSYS" not in json.loads(invoke(tmp_path, backend, args).stdout)["message"]


def test_reconnecting_keeps_the_bridge(tmp_path):
    (tmp_path / "shop.json").write_text(json.dumps(
        {"host": "old", "bridge_url": "https://shop.at", "bridge_token": "5.secret"}), encoding="utf-8")
    out = json.loads(invoke(tmp_path).stdout)
    saved = json.loads((tmp_path / "shop.json").read_text(encoding="utf-8"))
    assert out["replaced"] is True
    assert saved["host"] == "h" and saved["bridge_token"] == "5.secret"


def test_a_broken_session_file_is_repaired_not_a_crash(tmp_path):
    """load_session raised on an empty file, so reconnecting crashed."""
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
    camelCase was an undocumented break."""
    backend = MagicMock(**{"run.return_value": {
        "stdout": "Contao 5.7.13",
        "stderr": "Warning: Permanently added 'h' (ED25519) to the list of known hosts.",
        "returncode": 0,
    }})
    out = json.loads(invoke(tmp_path, backend).stdout)
    assert "host_key_accepted" in out and "hostKeyAccepted" not in out
    assert "h" in out["host_key_accepted"]
