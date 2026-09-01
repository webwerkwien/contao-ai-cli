"""
Unit tests for contao-ai-cli.
No SSH required — all tests use synthetic data.
"""
import json
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from contao_ai_cli.core import session as session_mod
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.contao_cli import cli


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


# ─── table_parser ─────────────────────────────────────────────────────────────

from contao_ai_cli.utils.table_parser import parse_table


class TestTableParser:
    def test_parse_table_basic(self):
        text = (
            " ---- ----------- \n"
            "  id   username   \n"
            " ---- ----------- \n"
            "  1    j.smith    \n"
            "  2    d.evans    \n"
            " ---- ----------- \n"
        )
        result = parse_table(text)
        assert result == [
            {"id": "1", "username": "j.smith"},
            {"id": "2", "username": "d.evans"},
        ]

    def test_parse_table_empty(self):
        assert parse_table("no table here") == []

    def test_parse_table_single_row(self):
        text = (
            " ---- ------- \n"
            "  id   title  \n"
            " ---- ------- \n"
            "  5    Home   \n"
            " ---- ------- \n"
        )
        result = parse_table(text)
        assert len(result) == 1
        assert result[0]["id"] == "5"
        assert result[0]["title"] == "Home"


# ─── member ───────────────────────────────────────────────────────────────────

from contao_ai_cli.core.member import member_list, member_create

MEMBER_TABLE = (
    " ---- ---------- --------------------- ----------- ---------- --------- \n"
    "  id   username   email                 firstname   lastname   disable  \n"
    " ---- ---------- --------------------- ----------- ---------- --------- \n"
    "  1    j.smith    j.smith@example.com   John        Smith      0        \n"
    " ---- ---------- --------------------- ----------- ---------- --------- \n"
)


class TestMember:
    def test_member_list_goes_through_record_list(self):
        backend = json_backend()
        member_list(backend)
        cmd = sent(backend)
        assert cmd.startswith("contao:record:list tl_member")
        assert "--fields=id,username,email,firstname,lastname,disable" in cmd
    def test_member_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": '{"status": "created", "username": "jdoe"}', "returncode": 0}
        result = member_create(backend, "jdoe", "secret", "Jane", "Doe", "jdoe@example.com")
        assert result["status"] == "created"
        assert result["username"] == "jdoe"


# ─── page ─────────────────────────────────────────────────────────────────────

from contao_ai_cli.core.page import page_list, page_tree

PAGE_TABLE = (
    " ---- ----- ------- -------- --------- ----------- \n"
    "  id   pid   title   alias    type      published   \n"
    " ---- ----- ------- -------- --------- ----------- \n"
    "  1    0     Root    root     root      1           \n"
    "  2    1     Home    index    regular   1           \n"
    "  3    2     Sub     sub      regular   1           \n"
    " ---- ----- ------- -------- --------- ----------- \n"
)


def json_backend(payload: str = '{"status":"ok","results":[]}'):
    """A backend whose console answers JSON, like every listing now does."""
    b = MagicMock()
    b.run.return_value = {"stdout": payload, "returncode": 0, "stderr": ""}
    return b


def sent(backend) -> str:
    return backend.run.call_args[0][0]

class TestPage:
    """The listing and the tree both moved off hand-written SQL (2026-09-01).

    What is pinned here is the command string, because that is the contract with
    the bundle. The rules behind it — which columns exist, what a filter may
    say — live in the DCA and are tested on the server.
    """

    def test_page_list_goes_through_record_list(self):
        backend = json_backend()
        page_list(backend)
        cmd = sent(backend)
        assert cmd.startswith("contao:record:list tl_page")
        assert "--fields=id,pid,title,alias,type,published,hide" in cmd
        assert "--order=" in cmd

    def test_page_list_filters_by_parent(self):
        backend = json_backend()
        page_list(backend, pid=1)
        assert "--filter=pid=1" in sent(backend)

    def test_page_list_passes_limit_and_offset(self):
        backend = json_backend()
        page_list(backend, None, 50, 100)
        cmd = sent(backend)
        assert "--limit=50" in cmd
        assert "--offset=100" in cmd

    def test_page_tree_uses_the_server_command(self):
        """The tree is built server-side; record:list caps at 100 rows and a
        real site passes that (wienerwandern.at has 283 pages)."""
        backend = json_backend()
        page_tree(backend)
        assert sent(backend) == "contao:page:tree"

    def test_page_tree_passes_root_and_depth(self):
        backend = json_backend()
        page_tree(backend, root=5, depth=4)
        cmd = sent(backend)
        assert "--root=5" in cmd
        assert "--depth=4" in cmd


# ─── article ──────────────────────────────────────────────────────────────────

from contao_ai_cli.core.article import article_list

ARTICLE_TABLE = (
    " ---- ----- ------- -------- ----------- --------- \n"
    "  id   pid   title   alias    published   inColumn  \n"
    " ---- ----- ------- -------- ----------- --------- \n"
    "  1    2     Home    index    1           main      \n"
    " ---- ----- ------- -------- ----------- --------- \n"
)


class TestArticle:
    def test_article_list_goes_through_record_list(self):
        backend = json_backend()
        article_list(backend)
        cmd = sent(backend)
        assert cmd.startswith("contao:record:list tl_article")
        assert "--fields=id,pid,title,alias,published,inColumn" in cmd
    def test_article_list_filters_by_page(self):
        backend = json_backend()
        article_list(backend, page_id=2)
        assert "--filter=pid=2" in sent(backend)


# ─── dca_schema resolve_callback_options ──────────────────────────────────────

from contao_ai_cli.core import dca_schema


def _write_schema(path, table, fields):
    """Helper: write a minimal schema JSON to path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump({'table': table, 'fetched': '2026-01-01T00:00:00', 'fields': fields}, f)

class TestResolveCallbackOptions:
    def test_static_language_resolved(self, tmp_dir):
        session_path = os.path.join(tmp_dir, 'c5.json')
        schema_path = os.path.join(tmp_dir, 'schemas', 'c5', 'tl_user.json')
        _write_schema(schema_path, 'tl_user', {
            'language': {'inputType': 'select', 'mandatory': True, 'options': '__callback__'},
        })
        backend = MagicMock()
        result = dca_schema.resolve_callback_options(backend, 'tl_user', session_path)
        assert 'language' in result
        assert isinstance(result['language'], dict)
        assert result['language']['de'] == 'German'
        assert result['language']['en'] == 'English'
        backend.run.assert_not_called()

    def test_table_based_groups_resolved(self, tmp_dir):
        session_path = os.path.join(tmp_dir, 'c5.json')
        schema_path = os.path.join(tmp_dir, 'schemas', 'c5', 'tl_user.json')
        _write_schema(schema_path, 'tl_user', {
            'groups': {'inputType': 'checkbox', 'mandatory': False, 'options': '__callback__'},
        })
        backend = MagicMock()
        backend.run.return_value = {
            'stdout': (
                " ---- ----------- \n"
                "  id   name       \n"
                " ---- ----------- \n"
                "  1    Admins     \n"
                "  2    Editors    \n"
                " ---- ----------- \n"
            ),
            'returncode': 0,
        }
        result = dca_schema.resolve_callback_options(backend, 'tl_user', session_path)
        assert result['groups'] == {'1': 'Admins', '2': 'Editors'}

    def test_unknown_callback_stays_unresolved(self, tmp_dir):
        session_path = os.path.join(tmp_dir, 'c5.json')
        schema_path = os.path.join(tmp_dir, 'schemas', 'c5', 'tl_user.json')
        _write_schema(schema_path, 'tl_user', {
            'modules': {'inputType': 'checkbox', 'mandatory': False, 'options': '__callback__'},
        })
        backend = MagicMock()
        result = dca_schema.resolve_callback_options(backend, 'tl_user', session_path)
        assert result['modules'] == '__unresolved__'

    def test_no_schema_raises(self, tmp_dir):
        session_path = os.path.join(tmp_dir, 'c5.json')
        backend = MagicMock()
        with pytest.raises(ValueError, match="No schema"):
            dca_schema.resolve_callback_options(backend, 'tl_user', session_path)

    def test_schema_updated_on_disk(self, tmp_dir):
        session_path = os.path.join(tmp_dir, 'c5.json')
        schema_path = os.path.join(tmp_dir, 'schemas', 'c5', 'tl_user.json')
        _write_schema(schema_path, 'tl_user', {
            'language': {'inputType': 'select', 'mandatory': True, 'options': '__callback__'},
        })
        backend = MagicMock()
        dca_schema.resolve_callback_options(backend, 'tl_user', session_path)
        updated = json.load(open(schema_path))
        assert updated['fields']['language']['options'] != '__callback__'
        assert isinstance(updated['fields']['language']['options'], dict)

    def test_page_type_resolved(self, tmp_dir):
        session_path = os.path.join(tmp_dir, 'c5.json')
        schema_path = os.path.join(tmp_dir, 'schemas', 'c5', 'tl_page.json')
        _write_schema(schema_path, 'tl_page', {
            'type': {'inputType': 'select', 'mandatory': False, 'options': '__callback__'},
        })
        backend = MagicMock()
        result = dca_schema.resolve_callback_options(backend, 'tl_page', session_path)
        assert 'regular' in result['type']
        assert 'root' in result['type']

    def test_single_field_resolve(self, tmp_dir):
        session_path = os.path.join(tmp_dir, 'c5.json')
        schema_path = os.path.join(tmp_dir, 'schemas', 'c5', 'tl_user.json')
        _write_schema(schema_path, 'tl_user', {
            'language': {'inputType': 'select', 'mandatory': True, 'options': '__callback__'},
            'modules':  {'inputType': 'checkbox', 'mandatory': False, 'options': '__callback__'},
        })
        backend = MagicMock()
        result = dca_schema.resolve_callback_options(backend, 'tl_user', session_path,
                                                     field='language')
        assert 'language' in result
        assert 'modules' not in result
