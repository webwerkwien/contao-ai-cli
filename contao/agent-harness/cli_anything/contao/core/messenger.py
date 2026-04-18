"""Symfony Messenger / message queue operations."""
from cli_anything.contao.utils.contao_backend import ContaoBackend


def messenger_stats(backend: ContaoBackend) -> dict:
    result = backend.run("messenger:stats")
    return {"output": result["stdout"]}


def messenger_failed_show(backend: ContaoBackend) -> dict:
    result = backend.run("messenger:failed:show")
    return {"output": result["stdout"]}


def messenger_failed_retry(backend: ContaoBackend, message_id: str = "") -> dict:
    cmd = "messenger:failed:retry --no-interaction"
    if message_id:
        cmd += f" {message_id}"
    result = backend.run(cmd)
    return {"status": "retried", "output": result["stdout"]}


def messenger_stop_workers(backend: ContaoBackend) -> dict:
    result = backend.run("messenger:stop-workers")
    return {"status": "stopping", "output": result["stdout"]}
