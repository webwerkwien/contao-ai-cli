"""
messenger group — Symfony Messenger / message queue operations.
"""
import click

from cli_anything.contao.core import messenger as messenger_mod
from .helpers import _get_backend, _output


@click.group()
def messenger():
    """Symfony Messenger / message queue operations."""


@messenger.command("stats")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def messenger_stats(ctx, as_json):
    """Show message count for transports."""
    b = _get_backend(ctx.obj.get("session"))
    _output(messenger_mod.messenger_stats(b), as_json or ctx.obj.get("as_json"))


@messenger.command("failed")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def messenger_failed(ctx, as_json):
    """Show failed messages."""
    b = _get_backend(ctx.obj.get("session"))
    _output(messenger_mod.messenger_failed_show(b), as_json or ctx.obj.get("as_json"))


@messenger.command("retry")
@click.argument("message_id", default="")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def messenger_retry(ctx, message_id, as_json):
    """Retry failed messages."""
    b = _get_backend(ctx.obj.get("session"))
    _output(messenger_mod.messenger_failed_retry(b, message_id),
            as_json or ctx.obj.get("as_json"))


@messenger.command("remove")
@click.argument("message_id")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def messenger_remove(ctx, message_id, as_json):
    """Remove a failed message by ID."""
    b = _get_backend(ctx.obj.get("session"))
    _output(messenger_mod.messenger_failed_remove(b, message_id),
            as_json or ctx.obj.get("as_json"))


@messenger.command("consume")
@click.argument("transport", default="")
@click.option("--limit", type=int, default=0, help="Stop after N messages")
@click.option("--time-limit", type=int, default=0, help="Stop after N seconds")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def messenger_consume(ctx, transport, limit, time_limit, as_json):
    """Consume messages from a transport (runs until stopped or limit reached)."""
    b = _get_backend(ctx.obj.get("session"))
    _output(messenger_mod.messenger_consume(b, transport, limit, time_limit),
            as_json or ctx.obj.get("as_json"))


@messenger.command("stop-workers")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def messenger_stop(ctx, as_json):
    """Stop all messenger worker processes."""
    b = _get_backend(ctx.obj.get("session"))
    _output(messenger_mod.messenger_stop_workers(b), as_json or ctx.obj.get("as_json"))
