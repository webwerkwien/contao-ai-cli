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

# Large themes carry their files/; packing, moving and importing them takes a while.
SERVER_TIMEOUT = 600
TRANSFER_TIMEOUT = 300

THEME_EXTENSIONS = (".cto", ".zip")
EXAMPLE_EXTENSIONS = (".sql", ".cto", ".zip")


class ArchiveError(Exception):
    """A transfer or server step that failed; the message says which."""


def _answer(backend: ContaoBackend, result: dict) -> dict:
    """The last JSON line of a command's stdout — PHP warnings can come first.

    Without one, the failure as text, with the hint when the command is missing (an older
    core-bundle), as file.py and contao_ops.py give it.
    """
    for line in reversed((result.get("stdout") or "").splitlines()):
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        if isinstance(answer, dict):
            return answer
    text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".strip()
    hint = backend.undefined_command_hint(result.get("stdout", ""), result.get("stderr", ""))
    raise ArchiveError((text[:400] or f"exit {result.get('returncode')}") + hint)


def _remove(backend: ContaoBackend, relative: str) -> None:
    try:
        backend.run_raw(f"rm -f {shlex.quote(relative)}")
    except Exception:
        pass


def theme_export(backend: ContaoBackend, theme_id: int, local_path: str | None = None) -> dict:
    """Export a theme and download its .cto; the server's copy is removed.

    Without `local_path` the file is named after the theme here, and an existing file of
    that name is not overwritten (in a draft a second export of the same theme
    replaced the first without a word).
    """
    default_name = not local_path
    answer = _answer(backend, backend.run(f"contao:theme:export {int(theme_id)}", check=False, timeout=SERVER_TIMEOUT))
    if answer.get("status") != "ok":
        return answer

    remote = str(answer["file"])
    if not re.fullmatch(r"system/tmp/[0-9a-f]+\.cto", remote):
        raise ArchiveError(f"Unexpected export path from the server: {remote!r}")

    try:
        if default_name:
            slug = re.sub(r"[^A-Za-z0-9_-]+", "-", str(answer.get("theme") or f"theme-{theme_id}")).strip("-")
            local_path = f"{slug or 'theme'}.cto"
            if os.path.exists(local_path):
                raise ArchiveError(f"{local_path} exists here already; pass --to to choose the file (an explicit --to overwrites).")
        result = backend.scp_download(f"{backend.contao_root}/{remote}", local_path, TRANSFER_TIMEOUT)
        if result.get("returncode", 0) != 0:
            raise ArchiveError(f"Download failed: {result.get('stderr', '')}")
    finally:
        _remove(backend, remote)

    return {"status": "ok", "theme": answer.get("theme"), "file": os.path.abspath(local_path),
            "size": os.path.getsize(local_path), "note": answer.get("note")}


class Upload:
    """A local file in system/tmp on the server for as long as the `with` lasts."""

    def __init__(self, backend: ContaoBackend, local_path: str, extensions: tuple[str, ...]):
        self.backend = backend
        self.local_path = local_path
        ext = os.path.splitext(local_path)[1].lower()
        # Checked here, before anything moves: the extension also ends up in the remote
        # file name, and a wrong type is better refused than uploaded.
        if ext not in extensions:
            raise ArchiveError(f"Not a {' / '.join(extensions)} file: {local_path}")
        self.relative = f"{TMP_DIR}/contao-ai-{uuid.uuid4().hex}{ext}"

    def __enter__(self) -> str:
        if not os.path.isfile(self.local_path):
            raise ArchiveError(f"Local file not found: {self.local_path}")
        self.backend.run_raw(f"mkdir -p {shlex.quote(TMP_DIR)}")
        try:
            result = self.backend.scp_upload(self.local_path, f"{self.backend.contao_root}/{self.relative}", TRANSFER_TIMEOUT)
            if result.get("returncode", 0) != 0:
                raise ArchiveError(f"Upload failed: {result.get('stderr', '')}")
        except BaseException:
            # __exit__ does not run when __enter__ fails; a half-written file would stay.
            self._cleanup()
            raise
        return self.relative

    def __exit__(self, *exc) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        _remove(self.backend, self.relative)
        # The example website the server extracts from an archive, named after it
        # (core-bundle ExampleWebsite::sqlFile()).
        _remove(self.backend, f"{os.path.splitext(self.relative)[0]}-example.sql")


def theme_import(backend: ContaoBackend, remote: str, confirm: bool, operator: str = "") -> dict:
    cmd = f"contao:theme:import {shlex.quote(remote)}"
    if confirm:
        cmd += " --confirm"
    if operator:
        cmd += f" --operator={shlex.quote(operator)}"
    return _answer(backend, backend.run(cmd, check=False, timeout=SERVER_TIMEOUT))


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
    return _answer(backend, backend.run(cmd, check=False, timeout=SERVER_TIMEOUT))
