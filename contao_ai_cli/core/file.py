"""Contao file manager (tl_files / DBAFS).

tl_files is the Database-Assisted File System (DBAFS) table.
It stores metadata for files and folders under the configured upload path.
"""
import json
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.core.contao_ops import record_list, run_json_or_raw, build_set_args, join_args


def file_list(backend: ContaoBackend, path: str | None = None,
              type_filter: str | None = None, limit=None, offset=None) -> dict:
    """List files from the DBAFS. Optionally scope to a path prefix and/or type.

    The path used to become `path LIKE '<value>%'` with the value pasted into
    the SQL. It is a bound parameter now, and a percent sign inside it stays
    literal instead of turning the listing into a full table scan.
    """
    return record_list(
        backend, "tl_files",
        fields=["id", "path", "name", "type", "extension", "hash", "found", "lastModified"],
        filters=[f"type={type_filter}"] if type_filter else None,
        prefixes=[f"path={path}"] if path else None,
        order="path ASC",
        limit=limit, offset=offset,
    )


def file_sync(backend: ContaoBackend) -> dict:
    """Synchronize the DBAFS with the virtual filesystem (contao:filesync)."""
    result = backend.run("contao:filesync")
    return {"status": "ok", "output": result["stdout"].strip()}


def folder_create(backend: ContaoBackend, path: str) -> dict:
    """Create a folder in the Contao file system via contao-ai-core-bundle."""
    return run_json_or_raw(backend, f'contao:folder:create --path {shlex.quote(path)}')


def file_process(
    backend: ContaoBackend,
    path: str,
    allowed_types: str = "",
    max_width: int = 0,
    max_height: int = 0,
    max_file_size: int = 0,
) -> dict:
    """Validate and optionally resize a file already on the server."""
    cmd = f'contao:file:process --path {shlex.quote(path)}'
    if allowed_types:
        cmd += f' --allowed-types {shlex.quote(allowed_types)}'
    if max_width:
        cmd += f' --max-width {max_width}'
    if max_height:
        cmd += f' --max-height {max_height}'
    if max_file_size:
        cmd += f' --max-file-size {max_file_size}'
    return run_json_or_raw(backend, cmd)


def file_write(backend: ContaoBackend, path: str, content: str) -> dict:
    """Write text content to a file under files/ via contao-ai-core-bundle.

    Uploads content via SCP to a temp file, then calls contao:file:write.
    Creates a tl_version snapshot if the file is already registered in DBAFS.
    """
    import os
    import tempfile

    # Write content to a local temp file, then SCP it to the server
    with tempfile.NamedTemporaryFile(mode='w', suffix='.tmp', delete=False, encoding='utf-8') as f:
        f.write(content)
        local_tmp = f.name

    try:
        # SCP the temp file to var/bridge-uploads/ in the Contao root
        upload_dir = f'{backend.contao_root}/var/bridge-uploads'
        backend.run_raw(f'mkdir -p {shlex.quote(upload_dir)}')
        basename = os.path.basename(local_tmp)
        remote_tmp = f'{upload_dir}/contao_write_{basename}'
        scp_result = backend.scp_upload(local_tmp, remote_tmp)
        if scp_result.get('returncode', 0) != 0:
            return {'status': 'error', 'message': f"SCP upload failed: {scp_result.get('stderr', '')}"}

        cmd = f'contao:file:write --path {shlex.quote(path)} --source {shlex.quote(remote_tmp)}'
        return run_json_or_raw(backend, cmd)
    finally:
        os.unlink(local_tmp)
        try:
            backend.run_raw(f'rm -f {shlex.quote(remote_tmp)}')
        except Exception:
            pass


def file_upload(backend: ContaoBackend, path: str, local_file: str) -> dict:
    """Upload any local file to files/ via contao-ai-core-bundle.

    The server holds it to the installation's own rules — uploadTypes,
    maxFileSize, image dimensions, SVG sanitising — the same ones a back-end
    upload goes through (core-bundle v0.13.0).

    Measured on 2026-09-16: `file write` could not carry a PNG. The transport
    was binary-safe all along — SCP, and the server reads bytes — only the
    local temp file was opened in text mode. So the local file is sent as it
    is, without a copy in between.
    """
    import os
    import uuid

    if not os.path.isfile(local_file):
        return {'status': 'error', 'message': f'Local file not found: {local_file}'}

    upload_dir = f'{backend.contao_root}/var/bridge-uploads'
    remote_tmp = f'{upload_dir}/contao_upload_{uuid.uuid4().hex}'
    backend.run_raw(f'mkdir -p {shlex.quote(upload_dir)}')

    try:
        scp_result = backend.scp_upload(local_file, remote_tmp)
        if scp_result.get('returncode', 0) != 0:
            return {'status': 'error', 'message': f"SCP upload failed: {scp_result.get('stderr', '')}"}

        cmd = f'contao:file:write --path {shlex.quote(path)} --source {shlex.quote(remote_tmp)}'
        return run_json_or_raw(backend, cmd)
    finally:
        try:
            backend.run_raw(f'rm -f {shlex.quote(remote_tmp)}')
        except Exception:
            pass


def folder_publish(backend: ContaoBackend, path: str, unpublish: bool = False) -> dict:
    """Make a folder public — or protect it again — as the back end does (core-bundle v0.13.0)."""
    cmd = f'contao:folder:publish --path {shlex.quote(path)}'
    if unpublish:
        cmd += ' --unpublish'
    return run_json_or_raw(backend, cmd)


def file_delete(backend: ContaoBackend, path: str, force: bool = False) -> dict:
    """Delete a file or folder below files/ with its DBAFS records (core-bundle v0.18.0).

    Refused while the file is still used — fileTree fields, insert tags or paths in text —
    unless force is set; the answer lists the usages either way. There is no undo.
    """
    cmd = f'contao:file:delete --path {shlex.quote(path)}'
    if force:
        cmd += ' --force'

    # check=False: a refusal exits 1 and carries `usages` — where the file is still
    # used. Letting run() raise kept only the message (measured on c5, 2026-09-16), so
    # the answer is returned as it came and the command sets the exit code.
    result = backend.run(cmd, check=False)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        if result.get("returncode", 0) != 0:
            # check=False bypasses run()'s own failure path, and with it the hint that
            # names the core-bundle version a missing command needs (review 2026-09-16).
            raise ContaoBackendError(
                f"file delete failed (exit {result['returncode']}): "
                f"{(result.get('stderr') or result['stdout'])[:500]}"
                f"{backend.undefined_command_hint(result['stdout'], result.get('stderr', ''))}"
            ) from None
        return {"raw": result["stdout"]}


def file_move(backend: ContaoBackend, path: str, to: str) -> dict:
    """Move a file or folder into another folder below files/ (core-bundle v0.23.0).

    As cut and paste in the back end: the name stays, the UUIDs stay, nothing is
    overwritten. `pathUsages` lists texts that name the old path — those break.
    """
    cmd = f'contao:file:move --path {shlex.quote(path)} --to {shlex.quote(to)}'
    # As file_delete: a refusal exits 1 with a message worth keeping as it came.
    result = backend.run(cmd, check=False)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        if result.get("returncode", 0) != 0:
            raise ContaoBackendError(
                f"file move failed (exit {result['returncode']}): "
                f"{(result.get('stderr') or result['stdout'])[:500]}"
                f"{backend.undefined_command_hint(result['stdout'], result.get('stderr', ''))}"
            ) from None
        return {"raw": result["stdout"]}


def file_read(backend: ContaoBackend, path: str) -> dict:
    """Read a text file from files/ on the server (UTF-8, max 512 KB)."""
    return run_json_or_raw(backend, f'contao:file:read --path {shlex.quote(path)}')


def file_meta_update(backend: ContaoBackend, path: str, meta: dict, lang: str = "en") -> dict:
    """Update tl_files metadata fields for a file or folder.

    lang: language key matching the Contao root-page language (default: en).
    """
    set_args = build_set_args(meta)
    cmd = join_args('contao:file:meta', '--path', shlex.quote(path),
                    '--lang', shlex.quote(lang), set_args)
    return run_json_or_raw(backend, cmd)
