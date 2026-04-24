import sys
import pytest
from unittest.mock import patch
from cli_anything.contao.utils.contao_backend import ContaoBackend


def make_backend():
    """Create a ContaoBackend instance for testing."""
    with patch.object(ContaoBackend, '_find_ssh', return_value="/usr/bin/ssh"), \
         patch.object(ContaoBackend, '_default_key', return_value="/home/user/.ssh/id_ed25519"):
        return ContaoBackend(
            host="example.com", user="deploy",
            contao_root="/var/www/contao",
            key_path="/home/user/.ssh/id_ed25519",
        )


def test_ssh_args_contains_control_master():
    """ControlMaster should be auto and ControlPersist set to 60s on non-Windows."""
    b = make_backend()
    args = b._ssh_args()
    args_str = " ".join(args)
    if sys.platform != "win32":
        assert "ControlMaster=auto" in args_str
        assert "ControlPersist" in args_str
    else:
        assert "ControlMaster" not in args_str


def test_ssh_args_uses_accept_new_host_checking():
    """StrictHostKeyChecking should be set to accept-new for security."""
    b = make_backend()
    args = b._ssh_args()
    args_str = " ".join(args)
    assert "StrictHostKeyChecking=accept-new" in args_str


def test_ssh_args_does_not_contain_no_host_checking():
    """StrictHostKeyChecking=no is insecure and must not be present."""
    b = make_backend()
    args = b._ssh_args()
    args_str = " ".join(args)
    assert "StrictHostKeyChecking=no" not in args_str


def test_init_caches_ssh_bin():
    """__init__ should cache _ssh_bin to avoid re-calling _find_ssh on each _ssh_args() call."""
    with patch.object(ContaoBackend, '_find_ssh', return_value="/usr/bin/ssh") as mock_find:
        b = ContaoBackend(
            host="example.com",
            user="deploy",
            contao_root="/var/www/contao",
            key_path="/home/user/.ssh/id_ed25519",
            port=22,
            php_path="php"
        )
        # _find_ssh should be called once during __init__
        assert mock_find.call_count == 1
        assert b._ssh_bin == "/usr/bin/ssh"
