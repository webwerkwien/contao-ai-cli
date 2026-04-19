"""Contao file manager (tl_files / DBAFS).

tl_files is the Database-Assisted File System (DBAFS) table.
It stores metadata for files and folders under the configured upload path.
"""
import json

from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


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
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def file_sync(backend: ContaoBackend) -> dict:
    """Synchronize the DBAFS with the virtual filesystem (contao:filesync)."""
    result = backend.run("contao:filesync")
    return {"status": "ok", "output": result["stdout"].strip()}


def folder_create(backend: ContaoBackend, path: str) -> dict:
    """Create a folder in the Contao file system via contao-cli-bridge."""
    cmd = f'contao:folder:create --path "{path}"'
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except Exception:
        return {"raw": result["stdout"]}


def file_process(
    backend: ContaoBackend,
    path: str,
    allowed_types: str = "",
    max_width: int = 0,
    max_height: int = 0,
    max_file_size: int = 0,
) -> dict:
    """Validate and optionally resize a file already on the server."""
    cmd = f'contao:file:process --path "{path}"'
    if allowed_types:
        cmd += f' --allowed-types "{allowed_types}"'
    if max_width:
        cmd += f' --max-width {max_width}'
    if max_height:
        cmd += f' --max-height {max_height}'
    if max_file_size:
        cmd += f' --max-file-size {max_file_size}'
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except Exception:
        return {"raw": result["stdout"]}


def file_meta_update(backend: ContaoBackend, path: str, meta: dict, lang: str = "en") -> dict:
    """Update tl_files metadata fields for a file or folder.

    lang: language key matching the Contao root-page language (default: en).
    """
    set_args = " ".join(f'--set "{k}={v}"' for k, v in meta.items())
    cmd = f'contao:file:meta --path "{path}" --lang "{lang}" {set_args}'
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except Exception:
        return {"raw": result["stdout"]}
