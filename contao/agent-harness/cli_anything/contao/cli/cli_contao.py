"""
contao group — Contao core operations.
"""
import click

from cli_anything.contao.core import contao_ops
from .helpers import _get_backend, _output


@click.group("contao")
def contao_group():
    """Contao core operations."""


@contao_group.command("migrate")
@click.option("--dry-run", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def migrate(ctx, dry_run, as_json):
    """Run database migrations."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.migrate(b, dry_run), as_json or ctx.obj.get("as_json"))


@contao_group.command("install")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def install(ctx, as_json):
    """Install required Contao directories."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.install(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("symlinks")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def symlinks(ctx, as_json):
    """Symlink public resources."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.symlinks(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("filesync")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def filesync(ctx, as_json):
    """Synchronize DBAFS with virtual filesystem."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.filesync(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("cron")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cron_run(ctx, as_json):
    """Run cron jobs."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.cron_run(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("cron-list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cron_list(ctx, as_json):
    """List available cron jobs."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.cron_list(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("maintenance")
@click.argument("action", type=click.Choice(["enable", "disable", "status"]))
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def maintenance(ctx, action, as_json):
    """Manage maintenance mode (enable/disable/status)."""
    b = _get_backend(ctx.obj.get("session"))
    if action == "enable":
        _output(contao_ops.maintenance_enable(b), as_json or ctx.obj.get("as_json"))
    elif action == "disable":
        _output(contao_ops.maintenance_disable(b), as_json or ctx.obj.get("as_json"))
    else:
        _output(contao_ops.maintenance_status(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("resize-images")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def resize_images(ctx, as_json):
    """Resize deferred images."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.resize_images(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("crawl")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def crawl(ctx, as_json):
    """Crawl the website (rebuild search index)."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.crawl(b), as_json or ctx.obj.get("as_json"))


@contao_group.command("automator")
@click.argument("task", default="")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def automator(ctx, task, as_json):
    """Run contao:automator tasks. TASK is optional (runs all if omitted)."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.automator(b, task), as_json or ctx.obj.get("as_json"))


@contao_group.command("setup")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def contao_setup(ctx, as_json):
    """Run post-install Contao setup."""
    b = _get_backend(ctx.obj.get("session"))
    _output(contao_ops.setup(b), as_json or ctx.obj.get("as_json"))
