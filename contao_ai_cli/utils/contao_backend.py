"""
SSH backend for Contao 5 CLI.
Wraps 'php bin/console' commands via SSH.
"""
import json
import os
import sys
import subprocess
import shutil
import shlex
from typing import Any

import click


class ContaoBackendError(click.ClickException):
    """Raised when a Contao backend command fails.

    A ClickException rather than a plain Exception, so that a failure the user
    can do something about — record not found, table has no DCA, SSH refused —
    prints as one `Error: ...` line and exits 1, instead of unwinding a Python
    traceback into the caller's terminal.

    Until 2026-08-31 only `connect` and `health` caught this; every other
    command let it through raw. An agent reading that output has to work out
    that the last line is the message and the twelve above it are noise, and
    `page read 99999` — an ordinary miss, not a defect — looked like a crash.

    Deliberately not swallowed: the exit code stays 1 and the message still
    goes to stderr, so scripts and pipelines behave exactly as before. Existing
    `except ContaoBackendError` handlers keep working, and `str(e)` still
    yields the message.
    """
    pass


class ContaoBackend:
    """
    Executes Contao Console commands on a remote server via SSH.
    The real software (Contao + PHP) is a hard dependency — this CLI
    is a structured interface TO Contao, not a replacement for it.
    """

    def __init__(self, host: str, user: str, contao_root: str,
                 key_path: str | None = None, port: int = 22,
                 php_path: str = "php"):
        self.host = host
        self.user = user
        self.contao_root = contao_root
        self.key_path = key_path or self._default_key()
        self.port = port
        self.php_path = php_path
        self._ssh_bin: str = self._find_ssh()  # cache — find_ssh called once

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

    def _ssh_args(self) -> list[str]:
        args = [
            self._ssh_bin,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            "-p", str(self.port),
        ]
        if sys.platform != "win32":
            control_path = os.path.expanduser(
                f"~/.ssh/cm-contao-{self.user}@{self.host}:{self.port}"
            )
            args += [
                "-o", "ControlMaster=auto",
                "-o", f"ControlPath={control_path}",
                "-o", "ControlPersist=60s",
            ]
        if self.key_path:
            args += ["-i", self.key_path]
        args.append(f"{self.user}@{self.host}")
        return args

    def run_raw(self, shell_command: str, timeout: int = 60) -> dict:
        """
        Run an arbitrary shell command on the remote server via SSH.
        Does NOT prepend 'php bin/console' — use for ls, find, etc.
        Returns dict with keys: returncode, stdout, stderr
        """
        full_cmd = f"cd {shlex.quote(self.contao_root)} && {shell_command}"
        ssh_cmd = self._ssh_args() + [full_cmd]
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"
        try:
            result = subprocess.run(ssh_cmd, capture_output=True, encoding="utf-8", errors="replace",
                                    env=env, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise ContaoBackendError(f"SSH command timed out after {timeout}s")
        output = {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        if result.returncode != 0:
            # shell_command may contain passwords — omit it from the error message
            raise ContaoBackendError(
                f"Shell command failed (exit {result.returncode}). "
                f"Stderr: {result.stderr.strip()[:500]}"
            )
        return output

    def run(self, command: str, json_output: bool = False, check: bool = True) -> dict:
        """
        Run a Contao console command via SSH.
        Returns dict with keys: returncode, stdout, stderr

        `check=False` returns the result instead of raising on a non-zero exit.
        Needed by the bulk update path: the server exits non-zero when any record
        failed, so a shell loop can notice — but its JSON summary is exactly what
        names the failures, and raising threw that away.
        """
        full_cmd = f"cd {shlex.quote(self.contao_root)} && {shlex.quote(self.php_path)} bin/console {command}"
        ssh_cmd = self._ssh_args() + [full_cmd]

        # Disable Git Bash / MSYS2 path conversion on Windows
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=60,
                # ssh would otherwise drain the caller's stdin. A `while read id;
                # do contao-ai-cli … ; done < ids.txt` loop then silently runs
                # exactly once and still reports success — 2026-08-29.
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            raise ContaoBackendError("SSH command timed out after 60s")

        output = {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

        if check and result.returncode != 0:
            truncated = command[:100] + ("..." if len(command) > 100 else "")
            raise ContaoBackendError(
                f"Command failed (exit {result.returncode}): {truncated}\n"
                f"{self._explain_failure(result.stdout, result.stderr)}"
            )

        if json_output:
            try:
                output["data"] = json.loads(result.stdout)
            except json.JSONDecodeError:
                output["data"] = result.stdout.strip()

        return output

    @staticmethod
    def _explain_failure(stdout: str, stderr: str) -> str:
        """Say why the command failed, preferring the server's own words.

        Every read and write command in the core bundle answers a failure with
        `{"status": "error", "message": "..."}` on stdout and then exits 1 —
        outputError() returns Command::FAILURE. Reporting only stderr therefore
        threw away the one part that says what happened and replaced it with
        whatever PHP had printed at startup. On c5 that is a warning about
        ionCube and a missing imagick.so, so `page read 99999` explained a
        missing record with an unrelated shared-library path.

        This is the same shape as the swallowed bulk-update summary of
        2026-08-29: the server exits non-zero *and* explains itself, and the
        exit code was allowed to discard the explanation. There it was fixed at
        one call site with check=False; here it belongs in the raise itself,
        because every command that can fail is affected.
        """
        try:
            payload = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            payload = None

        if isinstance(payload, dict) and payload.get("message"):
            return str(payload["message"])

        cleaned = (stderr or "").strip()
        return f"Stderr: {cleaned[:500]}" if cleaned else "No output from the server."

    def run_json(self, command: str) -> Any:
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

        args = [scp, "-o", "StrictHostKeyChecking=accept-new",
                "-o", "BatchMode=yes",
                "-P", str(self.port)]
        if self.key_path:
            args += ["-i", self.key_path]
        args += [local_path, f"{self.user}@{self.host}:{remote_path}"]

        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"

        try:
            result = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace",
                                    env=env, timeout=120, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise ContaoBackendError("SSH command timed out after 120s")
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
                f"Run: contao-ai-cli connect --host HOST --user USER "
                f"--root /path/to/contao"
            )
        with open(session_path, encoding="utf-8") as f:
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
