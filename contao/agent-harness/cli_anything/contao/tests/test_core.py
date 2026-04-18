"""
Unit tests for cli-anything-contao.
No SSH required — all tests use synthetic data.
"""
import json
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from cli_anything.contao.core import session as session_mod
from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.contao_cli import cli


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_session(tmp_dir):
    return {
        "host": "test.example.com",
        "user": "testuser",
        "contao_root": "/var/www/contao",
        "key_path": "/home/user/.ssh/id_ed25519",
        "port": 22,
        "php_path": "php",
    }


# ─── session.py ───────────────────────────────────────────────────────────────

class TestSession:
    def test_save_and_load_session(self, tmp_dir, sample_session):
        path = os.path.join(tmp_dir, "test.json")
        session_mod.save_session(sample_session, path)
        loaded = session_mod.load_session(path)
        assert loaded["host"] == "test.example.com"
        assert loaded["user"] == "testuser"
        assert loaded["contao_root"] == "/var/www/contao"

    def test_delete_session(self, tmp_dir, sample_session):
        path = os.path.join(tmp_dir, "delete_me.json")
        session_mod.save_session(sample_session, path)
        assert os.path.exists(path)
        session_mod.delete_session(path)
        assert not os.path.exists(path)

    def test_load_missing_session(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexistent.json")
        result = session_mod.load_session(path)
        assert result == {}

    def test_list_sessions(self, tmp_dir, sample_session):
        with patch.object(session_mod, "DEFAULT_SESSION_DIR", tmp_dir):
            path1 = os.path.join(tmp_dir, "session1.json")
            path2 = os.path.join(tmp_dir, "session2.json")
            session_mod.save_session({**sample_session, "host": "host1"}, path1)
            session_mod.save_session({**sample_session, "host": "host2"}, path2)
            sessions = session_mod.list_sessions()
            hosts = [s["host"] for s in sessions]
            assert "host1" in hosts
            assert "host2" in hosts

    def test_save_overwrites_existing(self, tmp_dir, sample_session):
        path = os.path.join(tmp_dir, "overwrite.json")
        session_mod.save_session(sample_session, path)
        updated = {**sample_session, "host": "new-host.example.com"}
        session_mod.save_session(updated, path)
        loaded = session_mod.load_session(path)
        assert loaded["host"] == "new-host.example.com"


# ─── contao_backend.py ────────────────────────────────────────────────────────

class TestContaoBackend:
    def test_missing_session_file_raises(self, tmp_dir):
        path = os.path.join(tmp_dir, "no_session.json")
        with pytest.raises(ContaoBackendError, match="Session file not found"):
            ContaoBackend.from_session(path)

    def test_incomplete_session_raises(self, tmp_dir):
        path = os.path.join(tmp_dir, "incomplete.json")
        with open(path, "w") as f:
            json.dump({"host": "example.com"}, f)  # missing user and contao_root
        with pytest.raises(ContaoBackendError, match="Missing"):
            ContaoBackend.from_session(path)

    def test_ssh_args_include_key(self):
        with patch("shutil.which", return_value="/usr/bin/ssh"):
            backend = ContaoBackend(
                host="example.com",
                user="testuser",
                contao_root="/var/www",
                key_path="/home/user/.ssh/id_ed25519",
            )
            args = backend._ssh_args()
            assert "-i" in args
            assert "/home/user/.ssh/id_ed25519" in args
            assert "testuser@example.com" in args

    def test_ssh_args_custom_port(self):
        with patch("shutil.which", return_value="/usr/bin/ssh"):
            backend = ContaoBackend(
                host="example.com",
                user="testuser",
                contao_root="/var/www",
                key_path="/fake/key",
                port=2222,
            )
            args = backend._ssh_args()
            assert "-p" in args
            assert "2222" in args

    def test_from_session_creates_backend(self, tmp_dir):
        path = os.path.join(tmp_dir, "valid.json")
        config = {
            "host": "example.com",
            "user": "testuser",
            "contao_root": "/var/www/contao",
            "key_path": "/fake/key",
            "port": 22,
            "php_path": "php",
        }
        with open(path, "w") as f:
            json.dump(config, f)
        with patch("shutil.which", return_value="/usr/bin/ssh"):
            backend = ContaoBackend.from_session(path)
            assert backend.host == "example.com"
            assert backend.user == "testuser"
            assert backend.contao_root == "/var/www/contao"


# ─── CLI help commands ────────────────────────────────────────────────────────

class TestCLIHelp:
    def setup_method(self):
        self.runner = CliRunner()

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "contao" in result.output.lower()

    def test_version(self):
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_cache_help(self):
        result = self.runner.invoke(cli, ["cache", "--help"])
        assert result.exit_code == 0
        assert "clear" in result.output

    def test_cache_clear_help(self):
        result = self.runner.invoke(cli, ["cache", "clear", "--help"])
        assert result.exit_code == 0

    def test_user_list_help(self):
        result = self.runner.invoke(cli, ["user", "list", "--help"])
        assert result.exit_code == 0

    def test_backup_help(self):
        result = self.runner.invoke(cli, ["backup", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "restore" in result.output

    def test_connect_missing_host(self):
        result = self.runner.invoke(cli, ["connect", "--user", "u", "--root", "/r"])
        assert result.exit_code != 0

    def test_contao_group_help(self):
        result = self.runner.invoke(cli, ["contao", "--help"])
        assert result.exit_code == 0
        assert "migrate" in result.output

    def test_debug_help(self):
        result = self.runner.invoke(cli, ["debug", "--help"])
        assert result.exit_code == 0

    def test_messenger_help(self):
        result = self.runner.invoke(cli, ["messenger", "--help"])
        assert result.exit_code == 0
