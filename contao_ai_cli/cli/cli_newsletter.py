"""
newsletter group — Manage Contao newsletters (tl_newsletter).
"""
import click

from contao_ai_cli.core import session as session_mod, newsletter as newsletter_mod
from .helpers import (
    _get_backend, _output, _require_core_bundle, bulk_id_options, confirm_delete,
    confirm_escalation, dispatch_update, parse_set_fields,
)


@click.group()
def newsletter():
    """Manage Contao newsletters (tl_newsletter)."""
    pass


@newsletter.command("channels")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def newsletter_channels(ctx, limit, offset):
    """List all newsletter channels."""
    _require_core_bundle(ctx, "newsletter channels")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.channel_list(b, limit, offset), ctx.obj.get("as_json"))


@newsletter.command("list")
@click.option("--channel", "channel_id", type=int, default=None,
              help="Filter by channel ID")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def newsletter_list_cmd(ctx, channel_id, limit, offset):
    """List newsletters, optionally filtered by channel ID."""
    _require_core_bundle(ctx, "newsletter list")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.newsletter_list(b, channel_id, limit, offset), ctx.obj.get("as_json"))


@newsletter.command("subscribers")
@click.option("--channel", "channel_id", type=int, default=None,
              help="Filter by channel ID")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def newsletter_subscribers(ctx, channel_id, limit, offset):
    """List newsletter subscribers."""
    _require_core_bundle(ctx, "newsletter subscribers")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.subscriber_list(b, channel_id, limit, offset), ctx.obj.get("as_json"))


# --- the channel: the root every newsletter and recipient hangs off -------


@newsletter.command("channel-create")
@click.option("--title", required=True, help="Channel title (back end label)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_channel_create_cmd(ctx, title, fields, as_json):
    """Create a newsletter channel.

    Only --title is an option here; what else is required comes from the DCA,
    so the command reports it rather than this help text going stale.
    (sender is the From address every newsletter in this channel is sent from.)
    """
    _require_core_bundle(ctx, "newsletter channel-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(newsletter_mod.channel_create(b, title, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@newsletter.command("channel-update")
@click.argument("channel_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_channel_update_cmd(ctx, channel_id, ids, ids_from_file, fields, as_json):
    """Update a newsletter channel, or many at once."""
    _require_core_bundle(ctx, "newsletter channel-update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:newsletter-channel:update", channel_id,
                            ids, ids_from_file, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@newsletter.command("channel-delete")
@click.argument("channel_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_channel_delete_cmd(ctx, channel_id, yes, as_json):
    """Delete a newsletter channel with its newsletters AND its recipients."""
    _require_core_bundle(ctx, "newsletter channel-delete")
    # Both child tables are named because the second one is the surprise: a
    # recipient list is the one thing here that exists nowhere else.
    if not confirm_delete(
        f"newsletter channel {channel_id}, every newsletter in it, "
        f"and its entire recipient list",
        yes,
    ):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(newsletter_mod.channel_delete(b, channel_id), as_json or ctx.obj.get("as_json"))


# --- the newsletter itself ------------------------------------------------


@newsletter.command("create")
@click.option("--subject", required=True, help="Newsletter subject")
@click.option("--pid", required=True, type=int, help="Newsletter channel ID")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_create_cmd(ctx, subject, pid, fields, as_json):
    """Create a newsletter in a channel.

    The alias is generated from the subject. Passing --set addFile=1 makes
    `files` mandatory, because it lives in that subpalette.
    """
    _require_core_bundle(ctx, "newsletter create")
    b = _get_backend(ctx.obj.get("session"))
    _output(newsletter_mod.newsletter_create(b, subject, pid, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@newsletter.command("update")
@click.argument("newsletter_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_update_cmd(ctx, newsletter_id, ids, ids_from_file, fields, as_json):
    """Update a newsletter, or many at once.

    `sent` and `date` are refused: they belong to Contao's send routine, and
    setting them marks a newsletter as sent without sending it. See
    `newsletter send`.
    """
    _require_core_bundle(ctx, "newsletter update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:newsletter:update", newsletter_id,
                            ids, ids_from_file, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@newsletter.command("delete")
@click.argument("newsletter_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_delete_cmd(ctx, newsletter_id, yes, as_json):
    """Delete a newsletter."""
    _require_core_bundle(ctx, "newsletter delete")
    if not confirm_delete(f"newsletter {newsletter_id}", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(newsletter_mod.newsletter_delete(b, newsletter_id), as_json or ctx.obj.get("as_json"))


# --- recipients -----------------------------------------------------------


@newsletter.command("subscriber-create")
@click.option("--email", required=True, help="Recipient e-mail address")
@click.option("--pid", required=True, type=int, help="Newsletter channel ID")
@click.option("--active", "active_flag", is_flag=True,
              help="Create the recipient active — they receive the next newsletter")
@click.option("--inactive", "inactive_flag", is_flag=True,
              help="Create the recipient inactive (the default when neither flag is given)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_subscriber_create_cmd(ctx, email, pid, active_flag, inactive_flag,
                                     fields, as_json):
    """Add a recipient to a newsletter channel.

    Applies the rules of Contao's own CSV import: valid address, no duplicate
    in the channel, and not on the channel's deny list. `addedOn` stays empty,
    so the back end shows the row as "added manually" rather than as an opt-in.

    Double opt-in in Contao guards the front end subscribe module, not this
    table — the back end and the CSV import both add active recipients without
    it. What it does mean is that the consent is yours, not the system's, so
    activating is asked rather than assumed: without --active or --inactive the
    command asks on a terminal and creates an INACTIVE recipient anywhere else.
    """
    _require_core_bundle(ctx, "newsletter subscriber-create")

    if active_flag and inactive_flag:
        raise click.UsageError("Give either --active or --inactive, not both.")

    if active_flag:
        active = True
    elif inactive_flag:
        active = False
    else:
        active = confirm_escalation(
            f"Create {email} as ACTIVE? They will receive the next newsletter "
            f"sent to this channel, with no double opt-in."
        )

    b = _get_backend(ctx.obj.get("session"))
    result = newsletter_mod.subscriber_create(b, email, pid, active, parse_set_fields(fields))

    if not active and not inactive_flag and not active_flag:
        click.echo(
            "Note: created INACTIVE. Nothing asked for confirmation here, so the safe "
            "option was taken. Pass --active to create an active recipient.",
            err=True,
        )

    _output(result, as_json or ctx.obj.get("as_json"))


@newsletter.command("subscriber-update")
@click.argument("recipient_id", type=int, required=False)
@bulk_id_options
@click.option("--set", "fields", multiple=True, required=True, metavar="FIELD=VALUE",
              help="Field to change; repeat for several fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_subscriber_update_cmd(ctx, recipient_id, ids, ids_from_file, fields, as_json):
    """Update a recipient, or many at once.

    The create rules apply here too: a changed address must be valid, unused in
    the channel and not on its deny list. Setting active=1 on a denied address
    is refused as well — stricter than the back end toggle, deliberately.
    """
    _require_core_bundle(ctx, "newsletter subscriber-update")
    b = _get_backend(ctx.obj.get("session"))
    _output(dispatch_update(b, "contao:newsletter-recipient:update", recipient_id,
                            ids, ids_from_file, parse_set_fields(fields)),
            as_json or ctx.obj.get("as_json"))


@newsletter.command("subscriber-delete")
@click.argument("recipient_id", type=int)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def newsletter_subscriber_delete_cmd(ctx, recipient_id, yes, as_json):
    """Remove a recipient from a channel.

    Not the same as unsubscribing: no deny list entry is written, so the
    address can be added again. For an opt-out request use
    `subscriber-update <id> --set active=0` or the back end's block action.
    """
    _require_core_bundle(ctx, "newsletter subscriber-delete")
    if not confirm_delete(f"newsletter recipient {recipient_id}", yes):
        raise click.Abort()
    b = _get_backend(ctx.obj.get("session"))
    _output(newsletter_mod.subscriber_delete(b, recipient_id), as_json or ctx.obj.get("as_json"))


# --- the one thing this CLI will not do -----------------------------------


@newsletter.command("send")
@click.argument("newsletter_id", type=int, required=False)
@click.pass_context
def newsletter_send_cmd(ctx, newsletter_id):
    """NOT AVAILABLE — sending stays with a person in the Contao back end.

    Registered on purpose so that asking for it produces a reason instead of
    "No such command", which reads like a gap worth working around.
    """
    raise click.ClickException(newsletter_mod.newsletter_send_refusal())
