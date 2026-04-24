"""
E2E tests for contao-cli-agent.
Requires: SSH access to a live Contao 5 installation.

Set environment variables:
  CONTAO_TEST_HOST     SSH host (e.g. your-server.example.com)
  CONTAO_TEST_USER     SSH user (e.g. ssh-username)
  CONTAO_TEST_ROOT     Contao root path on server
  CONTAO_TEST_KEY      SSH key path (optional, uses default)
"""
import json
import os
import sys
import shutil
import subprocess
import tempfile
import pytest

from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.core import session as session_mod, backup as backup_mod
from cli_anything.contao.core import cache as cache_mod, contao_ops, user as user_mod
from cli_anything.contao.core import debug_ops


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.contao.contao_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


def _skip_if_no_server():
    return pytest.mark.skipif(
        not os.environ.get("CONTAO_TEST_HOST"),
        reason="CONTAO_TEST_HOST not set — skipping live server tests"
    )


def _get_test_backend():
    host = os.environ.get("CONTAO_TEST_HOST")
    user = os.environ.get("CONTAO_TEST_USER")
    root = os.environ.get("CONTAO_TEST_ROOT", "/var/www/html")
    key = os.environ.get("CONTAO_TEST_KEY")
    if not host or not user:
        pytest.skip("CONTAO_TEST_HOST / CONTAO_TEST_USER not set")
    return ContaoBackend(host=host, user=user, contao_root=root, key_path=key)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def backend():
    return _get_test_backend()


@pytest.fixture
def saved_session(tmp_dir):
    path = os.path.join(tmp_dir, "test_session.json")
    host = os.environ.get("CONTAO_TEST_HOST")
    user = os.environ.get("CONTAO_TEST_USER")
    if not host or not user:
        pytest.skip("CONTAO_TEST_HOST / CONTAO_TEST_USER not set")
    config = {
        "host": host,
        "user": user,
        "contao_root": os.environ.get("CONTAO_TEST_ROOT", "/var/www/html"),
        "key_path": os.environ.get("CONTAO_TEST_KEY"),
        "port": 22,
        "php_path": "php",
    }
    session_mod.save_session(config, path)
    return path


# ─── Connection ───────────────────────────────────────────────────────────────

@_skip_if_no_server()
class TestConnection:
    def test_backend_version(self, backend):
        result = backend.run("--version")
        assert result["returncode"] == 0
        assert "Contao" in result["stdout"]
        print(f"\n  Contao version: {result['stdout']}")

    def test_about_command(self, backend):
        result = backend.run("about")
        assert result["returncode"] == 0
        assert "Symfony" in result["stdout"] or "PHP" in result["stdout"]


# ─── Cache ────────────────────────────────────────────────────────────────────

@_skip_if_no_server()
class TestCache:
    def test_cache_clear(self, backend):
        result = cache_mod.cache_clear(backend)
        assert result["status"] == "cleared"
        print(f"\n  cache:clear output: {result['output'][:100]}")

    def test_cache_pool_list(self, backend):
        result = cache_mod.cache_pool_list(backend)
        assert "raw" in result
        print(f"\n  cache pools: {result['raw'][:200]}")


# ─── Contao Operations ────────────────────────────────────────────────────────

@_skip_if_no_server()
class TestContaoOps:
    def test_migrate_dry_run(self, backend):
        result = contao_ops.migrate(backend, dry_run=True)
        assert result["status"] == "ok"
        assert result["dry_run"] is True
        print(f"\n  migrate --dry-run: {result['output'][:200]}")

    def test_maintenance_status(self, backend):
        result = contao_ops.maintenance_status(backend)
        assert "enabled" in result
        print(f"\n  maintenance status: {result}")

    def test_cron_list(self, backend):
        result = contao_ops.cron_list(backend)
        assert "output" in result
        print(f"\n  cron list: {result['output'][:300]}")

    def test_filesync(self, backend):
        result = contao_ops.filesync(backend)
        assert result["status"] == "ok"
        print(f"\n  filesync: {result['output'][:200]}")


# ─── Users ────────────────────────────────────────────────────────────────────

@_skip_if_no_server()
class TestUsers:
    def test_user_list_returns_data(self, backend):
        users = user_mod.user_list(backend)
        assert isinstance(users, list)
        assert len(users) > 0
        assert "username" in users[0]
        print(f"\n  users: {[u['username'] for u in users]}")


# ─── Backup ───────────────────────────────────────────────────────────────────

@_skip_if_no_server()
class TestBackup:
    def test_backup_list(self, backend):
        result = backup_mod.backup_list(backend)
        assert "output" in result
        print(f"\n  backup list: {result['output'][:300]}")

    def test_backup_create(self, backend):
        result = backup_mod.backup_create(backend)
        assert result["status"] == "created"
        print(f"\n  backup created: {result['output'][:200]}")


# ─── Debug ────────────────────────────────────────────────────────────────────

@_skip_if_no_server()
class TestDebug:
    def test_debug_plugins(self, backend):
        result = debug_ops.debug_plugins(backend)
        assert "output" in result
        print(f"\n  debug:plugins: {result['output'][:300]}")

    def test_debug_pages(self, backend):
        result = debug_ops.debug_pages(backend)
        assert "output" in result
        print(f"\n  debug:pages: {result['output'][:300]}")


# ─── CLI Subprocess tests ─────────────────────────────────────────────────────

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("contao-cli-agent")

    def _run(self, args, check=False):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True, check=check
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "contao" in result.stdout.lower()

    def test_version(self):
        result = self._run(["--version"])
        assert result.returncode == 0

    def test_cache_help(self):
        result = self._run(["cache", "--help"])
        assert result.returncode == 0

    def test_user_help(self):
        result = self._run(["user", "--help"])
        assert result.returncode == 0

    def test_backup_help(self):
        result = self._run(["backup", "--help"])
        assert result.returncode == 0

    @_skip_if_no_server()
    def test_full_deployment_workflow(self, saved_session):
        """Scenario 1: Deployment pipeline via CLI subprocess."""
        base = self.CLI_BASE + ["--session", saved_session]

        # 1. Check maintenance status
        r = subprocess.run(base + ["contao", "maintenance", "status"],
                           capture_output=True, text=True)
        assert r.returncode == 0
        print(f"\n  maintenance status: {r.stdout[:100]}")

        # 2. Run migration dry-run
        r = subprocess.run(base + ["contao", "migrate", "--dry-run"],
                           capture_output=True, text=True)
        assert r.returncode == 0
        print(f"  migrate --dry-run: OK")

        # 3. Clear cache
        r = subprocess.run(base + ["cache", "clear"],
                           capture_output=True, text=True)
        assert r.returncode == 0
        print(f"  cache clear: OK")

        print("\n  Full deployment workflow: PASSED")

    @_skip_if_no_server()
    def test_json_output_user_list(self, saved_session):
        """User list returns valid JSON."""
        base = self.CLI_BASE + ["--session", saved_session, "--json"]
        r = subprocess.run(base + ["user", "list"],
                           capture_output=True, text=True)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert isinstance(data, list)
        print(f"\n  user list JSON: {len(data)} users")
