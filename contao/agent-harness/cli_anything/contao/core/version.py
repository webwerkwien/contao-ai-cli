"""Contao version history management (tl_version)."""
import json
import shlex

from cli_anything.contao.utils.contao_backend import ContaoBackend


def version_list(backend: ContaoBackend, table: str, record_id: int) -> dict:
    """List all version snapshots for a record."""
    cmd = f'contao:version:list --table {shlex.quote(table)} --id {record_id}'
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def version_read(backend: ContaoBackend, table: str, record_id: int, version: int) -> dict:
    """Read a specific version snapshot (data field deserialized as dict)."""
    cmd = f'contao:version:read --table {shlex.quote(table)} --id {record_id} --version {version}'
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def version_restore(backend: ContaoBackend, table: str, record_id: int, version: int) -> dict:
    """Restore a record to a specific version."""
    cmd = f'contao:version:restore --table {shlex.quote(table)} --id {record_id} --version {version}'
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def version_create(backend: ContaoBackend, table: str, record_id: int) -> dict:
    """Manually create a version snapshot for a record."""
    cmd = f'contao:version:create --table {shlex.quote(table)} --id {record_id}'
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}
