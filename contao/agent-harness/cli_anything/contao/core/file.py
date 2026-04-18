"""Contao file manager (tl_files / DBAFS).

tl_files is the Database-Assisted File System (DBAFS) table.
It stores metadata for files and folders under the configured upload path.
"""
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
