"""Contao file manager (tl_files / DBAFS).

tl_files is the Database-Assisted File System (DBAFS) table.
It stores metadata for files and folders under the configured upload path.
"""
import shlex

from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def file_list(backend: ContaoBackend, path: str = None, type_filter: str = None) -> list:
    """
    List files/folders from tl_files.

    path: optional path prefix to filter (e.g. 'files/images')
    type_filter: 'file' or 'folder' — omit for both
    """
    conditions = []
    if path:
        safe_path = path.replace("'", "''")
        conditions.append(f"path LIKE '{safe_path}%'")
    if type_filter in ("file", "folder"):
        conditions.append(f"type = '{type_filter}'")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        f"SELECT id, path, name, type, extension, hash, found, lastModified "
        f"FROM tl_files {where} ORDER BY path"
    )
    return run_sql_table(backend, sql)


def file_sync(backend: ContaoBackend) -> dict:
    """Synchronize the DBAFS with the virtual filesystem (contao:filesync)."""
    result = backend.run("contao:filesync")
    return {"status": "ok", "output": result["stdout"].strip()}


def folder_create(backend: ContaoBackend, path: str) -> dict:
    """Create a folder in the Contao file system via contao-cli-bridge."""
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
    """Write text content to a file under files/ via contao-cli-bridge.

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
        # SCP the temp file to /tmp on the server
        remote_tmp = f'/tmp/contao_write_{os.path.basename(local_tmp)}'
        scp_result = backend.scp_upload(local_tmp, remote_tmp)
        if scp_result.get('returncode', 0) != 0:
            return {'status': 'error', 'message': f"SCP upload failed: {scp_result.get('stderr', '')}"}

        cmd = f'contao:file:write --path {shlex.quote(path)} --source {shlex.quote(remote_tmp)}'
        return run_json_or_raw(backend, cmd)
    finally:
        os.unlink(local_tmp)


def file_read(backend: ContaoBackend, path: str) -> dict:
    """Read a text file from files/ on the server (UTF-8, max 512 KB)."""
    return run_json_or_raw(backend, f'contao:file:read --path {shlex.quote(path)}')


def file_meta_update(backend: ContaoBackend, path: str, meta: dict, lang: str = "en") -> dict:
    """Update tl_files metadata fields for a file or folder.

    lang: language key matching the Contao root-page language (default: en).
    """
    set_args = build_set_args(meta)
    cmd = f'contao:file:meta --path {shlex.quote(path)} --lang {shlex.quote(lang)} {set_args}'
    return run_json_or_raw(backend, cmd.strip())
