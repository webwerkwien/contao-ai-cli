"""Contao layout management (tl_layout)."""
import json

from cli_anything.contao.utils.contao_backend import ContaoBackend


def layout_read(backend: ContaoBackend, layout_id: int) -> dict:
    """Read all fields of a tl_layout record."""
    cmd = f"contao:layout:read {layout_id}"
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}
