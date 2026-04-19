"""
SSH backend for Contao 5 CLI.
Wraps 'php bin/console' commands via SSH.
"""
import json
import os
import sys
import subprocess
import shutil
from typing import Optional


class ContaoBackendError(Exception):
    """Raised when a Contao backend command fails."""
    pass


class ContaoBackend:
    """
    Executes Contao Console commands on a remote server via SSH.
    The real software (Contao + PHP) is a hard dependency — this CLI
    is a structured interface TO Contao, not a replacement for it.
    """

    def __init__(self, host: str, user: str, contao_root: str,
                 key_path: Optional[str] = None, port: int = 22,
                 php_path: str = "php"):
        self.host = host
        self.user = user
        self.contao_root = contao_root
        self.key_path = key_path or self._default_key()
        self.port = port
        self.php_path = php_path
        self._verify_ssh()

    def _default_key(self) -> str:
        candidates = [
            os.path.expanduser("~/.ssh/id_ed25519"),
            os.path.expanduser("~/.ssh/id_rsa"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        raise ContaoBackendError(
            "No SSH key found. Specify key_path in your session config."
        )

    def _find_ssh(self) -> str:
        """Find SSH binary. On Windows, prefer native OpenSSH to avoid MSYS path conversion."""
        if sys.platform == "win32":
            native = r"C:\Windows\System32\OpenSSH\ssh.exe"
            if os.path.exists(native):
                return native
        found = shutil.which("ssh")
        if not found:
            raise ContaoBackendError(
                "ssh not found. Install OpenSSH client."
            )
        return found

    def _verify_ssh(self):
        self._find_ssh()  # raises if not found

    def _ssh_args(self) -> list:
        args = [self._find_ssh(), "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-p", str(self.port)]
        if self.key_path:
            args += ["-i", self.key_path]
        args.append(f"{self.user}@{self.host}")
        return args

    def run_raw(self, shell_command: str) -> dict:
        """
        Run an arbitrary shell command on the remote server via SSH.
        Does NOT prepend 'php bin/console' — use for ls, find, etc.
        Returns dict with keys: returncode, stdout, stderr
        """
        full_cmd = f"cd '{self.contao_root}' && {shell_command}"
        ssh_cmd = self._ssh_args() + [full_cmd]
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, env=env)
        output = {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        if result.returncode != 0:
            raise ContaoBackendError(
                f"Shell command failed (exit {result.returncode}): {shell_command}\n"
                f"stderr: {result.stderr.strip()}"
            )
        return output

    def run(self, command: str, json_output: bool = False) -> dict:
        """
        Run a Contao console command via SSH.
        Returns dict with keys: returncode, stdout, stderr
        """
        full_cmd = f"cd '{self.contao_root}' && {self.php_path} bin/console {command}"
        ssh_cmd = self._ssh_args() + [full_cmd]

        # Disable Git Bash / MSYS2 path conversion on Windows
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"

        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            env=env,
        )

        output = {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

        if result.returncode != 0:
            raise ContaoBackendError(
                f"Command failed (exit {result.returncode}): {command}\n"
                f"stderr: {result.stderr.strip()}"
            )

        if json_output:
            try:
                output["data"] = json.loads(result.stdout)
            except json.JSONDecodeError:
                output["data"] = result.stdout.strip()

        return output

    def run_json(self, command: str) -> any:
        """Run command and parse JSON output. Appends --format=json if needed."""
        result = self.run(command)
        try:
            return json.loads(result["stdout"])
        except json.JSONDecodeError:
            return result["stdout"]

    def scp_upload(self, local_path: str, remote_path: str) -> dict:
        """Upload a local file to the remote server via SCP."""
        scp = shutil.which("scp")
        if sys.platform == "win32":
            native_scp = r"C:\Windows\System32\OpenSSH\scp.exe"
            if os.path.exists(native_scp):
                scp = native_scp
        if not scp:
            raise ContaoBackendError("scp not found. Install OpenSSH client.")

        args = [scp, "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-P", str(self.port)]
        if self.key_path:
            args += ["-i", self.key_path]
        args += [local_path, f"{self.user}@{self.host}:{remote_path}"]

        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"

        result = subprocess.run(args, capture_output=True, text=True, env=env)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    @classmethod
    def from_session(cls, session_path: str) -> "ContaoBackend":
        """Create a backend from a session config file."""
        if not os.path.exists(session_path):
            raise ContaoBackendError(
                f"Session file not found: {session_path}\n"
                f"Run: contao-cli-agent connect --host HOST --user USER "
                f"--root /path/to/contao"
            )
        with open(session_path) as f:
            cfg = json.load(f)
        required = ["host", "user", "contao_root"]
        for key in required:
            if key not in cfg:
                raise ContaoBackendError(f"Missing '{key}' in session config.")
        return cls(
            host=cfg["host"],
            user=cfg["user"],
            contao_root=cfg["contao_root"],
            key_path=cfg.get("key_path"),
            port=cfg.get("port", 22),
            php_path=cfg.get("php_path", "php"),
        )
