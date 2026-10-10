"""Translation links of terminal42/contao-changelanguage (core-bundle v1.4.0)."""
import json
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend


def _decode(result: dict) -> dict:
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def language_link(backend: ContaoBackend, table: str, record_id: int, main: int) -> dict:
    """Link a record to its counterpart in the main language; main 0 removes the link."""
    cmd = f'contao:language:link --table {shlex.quote(table)} --id {record_id} --main {main}'
    return _decode(backend.run(cmd))


def language_check(backend: ContaoBackend, root: int | None = None) -> dict:
    """Report missing or broken translation links. Reads only."""
    cmd = 'contao:language:check'
    if root:
        cmd += f' --root {root}'
    return _decode(backend.run(cmd))
