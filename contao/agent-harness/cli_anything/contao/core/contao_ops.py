"""Core Contao operations: migrate, crawl, cron, filesync, maintenance."""
from cli_anything.contao.utils.contao_backend import ContaoBackend


def migrate(backend: ContaoBackend, dry_run: bool = False) -> dict:
    cmd = "contao:migrate --no-interaction"
    if dry_run:
        cmd += " --dry-run"
    result = backend.run(cmd)
    return {"status": "ok", "dry_run": dry_run, "output": result["stdout"]}


def install(backend: ContaoBackend) -> dict:
    result = backend.run("contao:install --no-interaction")
    return {"status": "ok", "output": result["stdout"]}


def symlinks(backend: ContaoBackend) -> dict:
    result = backend.run("contao:symlinks")
    return {"status": "ok", "output": result["stdout"]}


def filesync(backend: ContaoBackend) -> dict:
    result = backend.run("contao:filesync")
    return {"status": "ok", "output": result["stdout"]}


def cron_run(backend: ContaoBackend) -> dict:
    result = backend.run("contao:cron")
    return {"status": "ok", "output": result["stdout"]}


def cron_list(backend: ContaoBackend) -> dict:
    result = backend.run("contao:cron:list")
    return {"output": result["stdout"]}


def maintenance_enable(backend: ContaoBackend) -> dict:
    result = backend.run("contao:maintenance-mode enable")
    return {"status": "enabled", "output": result["stdout"]}


def maintenance_disable(backend: ContaoBackend) -> dict:
    result = backend.run("contao:maintenance-mode disable")
    return {"status": "disabled", "output": result["stdout"]}


def maintenance_status(backend: ContaoBackend) -> dict:
    result = backend.run("contao:maintenance-mode status")
    enabled = "enabled" in result["stdout"].lower()
    return {"enabled": enabled, "output": result["stdout"]}


def resize_images(backend: ContaoBackend) -> dict:
    result = backend.run("contao:resize-images")
    return {"status": "ok", "output": result["stdout"]}


def crawl(backend: ContaoBackend) -> dict:
    result = backend.run("contao:crawl --no-interaction")
    return {"status": "ok", "output": result["stdout"]}
