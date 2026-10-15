"""Theme export/import and example websites (core-bundle v1.9.0).

The server runs Contao's own theme manager; this side moves the files. An archive goes
to system/tmp on the server (the only place the core-bundle reads it from) and is removed
again afterwards, an export comes back the same way.
"""
import json
import os
import re
import shlex
import uuid

from contao_ai_cli.utils.contao_backend import ContaoBackend

TMP_DIR = "system/tmp"


class ArchiveError(Exception):
    """A transfer or server step that failed; the message says which."""


def _answer(result: dict) -> dict:
    """The last JSON line of a command's stdout — PHP warnings can come first."""
    for line in reversed((result.get("stdout") or "").splitlines()):
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        if isinstance(answer, dict):
            return answer
    text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".strip()
    raise ArchiveError(text[:400] or f"exit {result.get('returncode')}")


def _remove(backend: ContaoBackend, relative: str) -> None:
    try:
        backend.run_raw(f"rm -f {shlex.quote(relative)}")
    except Exception:
        pass


def theme_export(backend: ContaoBackend, theme_id: int, local_path: str | None = None) -> dict:
    """Export a theme and download its .cto; the server's copy is removed."""
    answer = _answer(backend.run(f"contao:theme:export {int(theme_id)}", check=False))
    if answer.get("status") != "ok":
        return answer

    remote = str(answer["file"])
    if not re.fullmatch(r"system/tmp/[0-9a-f]+\.cto", remote):
        raise ArchiveError(f"Unexpected export path from the server: {remote!r}")

    if not local_path:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(answer.get("theme") or f"theme-{theme_id}")).strip("-")
        local_path = f"{slug or 'theme'}.cto"
    try:
        result = backend.scp_download(f"{backend.contao_root}/{remote}", local_path)
        if result.get("returncode", 0) != 0:
            raise ArchiveError(f"Download failed: {result.get('stderr', '')}")
    finally:
        _remove(backend, remote)

    return {"status": "ok", "theme": answer.get("theme"), "file": os.path.abspath(local_path),
            "size": os.path.getsize(local_path), "note": answer.get("note")}


class Upload:
    """A local file in system/tmp on the server for as long as the `with` lasts."""

    def __init__(self, backend: ContaoBackend, local_path: str):
        self.backend = backend
        self.local_path = local_path
        ext = os.path.splitext(local_path)[1].lower()
        self.relative = f"{TMP_DIR}/contao-ai-{uuid.uuid4().hex}{ext}"

    def __enter__(self) -> str:
        if not os.path.isfile(self.local_path):
            raise ArchiveError(f"Local file not found: {self.local_path}")
        self.backend.run_raw(f"mkdir -p {shlex.quote(TMP_DIR)}")
        result = self.backend.scp_upload(self.local_path, f"{self.backend.contao_root}/{self.relative}")
        if result.get("returncode", 0) != 0:
            raise ArchiveError(f"Upload failed: {result.get('stderr', '')}")
        return self.relative

    def __exit__(self, *exc) -> None:
        _remove(self.backend, self.relative)
        # An archive's example website, extracted next to it by the server. A fixed glob,
        # unquoted on purpose so the shell expands it; nothing of the caller's is in it.
        try:
            self.backend.run_raw(f"rm -f {TMP_DIR}/contao-ai-example-*.sql")
        except Exception:
            pass


def theme_import(backend: ContaoBackend, remote: str, confirm: bool, operator: str = "") -> dict:
    cmd = f"contao:theme:import {shlex.quote(remote)}"
    if confirm:
        cmd += " --confirm"
    if operator:
        cmd += f" --operator={shlex.quote(operator)}"
    return _answer(backend.run(cmd, check=False, timeout=600))


def example_import(backend: ContaoBackend, remote: str, mode: str, admins: str | None,
                   entry: str | None, confirm: bool, operator: str = "") -> dict:
    cmd = f"contao:example-website:import {shlex.quote(remote)} --mode={shlex.quote(mode)}"
    if admins:
        cmd += f" --admins={shlex.quote(admins)}"
    if entry:
        cmd += f" --entry={shlex.quote(entry)}"
    if confirm:
        cmd += " --confirm"
    if operator:
        cmd += f" --operator={shlex.quote(operator)}"
    return _answer(backend.run(cmd, check=False, timeout=600))
