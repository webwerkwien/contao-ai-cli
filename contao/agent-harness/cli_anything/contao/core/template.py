"""Contao Twig template management (templates/ directory)."""
import json
import os
import shlex
import tempfile

from cli_anything.contao.utils.contao_backend import ContaoBackend


def template_list(backend: ContaoBackend, prefix: str = "") -> dict:
    """List custom templates under templates/. Optionally filter by prefix."""
    cmd = "contao:template:list"
    if prefix:
        cmd += f" --prefix {shlex.quote(prefix)}"
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def template_read(backend: ContaoBackend, path: str) -> dict:
    """Read a template file from templates/ and return its content."""
    cmd = f"contao:template:read --path {shlex.quote(path)}"
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def template_write(backend: ContaoBackend, mode: str, base: str,
                   content: str, name: str = "") -> dict:
    """Write a Twig template via SCP + contao:template:write.

    mode: 'override' | 'partial' | 'variant'
    base: e.g. 'content_element/text'
    name: variant name (required for mode='variant')
    content: template source as string
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.twig', delete=False, encoding='utf-8') as f:
        f.write(content)
        local_tmp = f.name

    try:
        remote_tmp = f'/tmp/contao_tpl_{os.path.basename(local_tmp)}'
        scp_result = backend.scp_upload(local_tmp, remote_tmp)
        if scp_result.get('returncode', 0) != 0:
            return {'status': 'error', 'message': f"SCP upload failed: {scp_result.get('stderr', '')}"}

        cmd = (f"contao:template:write --mode {shlex.quote(mode)} "
               f"--base {shlex.quote(base)} --source {shlex.quote(remote_tmp)}")
        if name:
            cmd += f" --name {shlex.quote(name)}"

        result = backend.run(cmd)
        try:
            return json.loads(result["stdout"])
        except json.JSONDecodeError:
            return {"raw": result["stdout"]}
    finally:
        os.unlink(local_tmp)
        try:
            backend.run_raw(f'rm -f {shlex.quote(remote_tmp)}')
        except Exception:
            pass
