"""Contao newsletter management (tl_newsletter, tl_newsletter_channel).

Sending is deliberately absent — see `newsletter_send_refusal()` at the bottom
of this module for the reasoning and the message an agent gets instead.
"""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    record_list, run_json_or_raw, build_set_args, run_update, run_delete,
)


def channel_list(backend: ContaoBackend, limit=None, offset=None) -> dict:
    """List all newsletter channels (tl_newsletter_channel)."""
    return record_list(
        backend, "tl_newsletter_channel",
        fields=["id", "title"], order="title ASC",
        limit=limit, offset=offset,
    )


def newsletter_list(backend: ContaoBackend, channel_id: int | None = None,
                    limit=None, offset=None) -> dict:
    """List newsletters. Optionally filter by channel ID (pid)."""
    return record_list(
        backend, "tl_newsletter",
        fields=["id", "pid", "subject", "alias", "sent", "date"],
        filters=[f"pid={int(channel_id)}"] if channel_id is not None else None,
        order="date DESC",
        limit=limit, offset=offset,
    )


def subscriber_list(backend: ContaoBackend, channel_id: int | None = None,
                    limit=None, offset=None) -> dict:
    """List newsletter subscribers (tl_newsletter_recipients)."""
    return record_list(
        backend, "tl_newsletter_recipients",
        fields=["id", "pid", "email", "active"],
        filters=[f"pid={int(channel_id)}"] if channel_id is not None else None,
        order="email ASC",
        limit=limit, offset=offset,
    )


def channel_create(backend: ContaoBackend, title: str,
                   fields: dict | None = None) -> dict:
    """Create a newsletter channel.

    `title` and `sender` are both mandatory — the second one is passed through
    --set and refused server-side if missing, with `sender` named in the error.
    """
    cmd = f"contao:newsletter-channel:create --title={shlex.quote(title)} --no-interaction"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def channel_update(backend: ContaoBackend, channel_id: int, fields: dict) -> dict:
    """Update a newsletter channel."""
    return run_update(backend, "contao:newsletter-channel:update", channel_id, fields)


def channel_delete(backend: ContaoBackend, channel_id: int) -> dict:
    """Delete a newsletter channel with everything under it.

    Chain: tl_newsletter AND tl_newsletter_recipients — two child tables, and
    the recipient list is the one nobody pictures from the command name. One
    `tl_undo` entry for the set.
    """
    return run_delete(backend, "contao:newsletter-channel:delete", channel_id)


# --- the newsletter itself ------------------------------------------------


def newsletter_create(backend: ContaoBackend, subject: str, pid: int,
                      fields: dict | None = None) -> dict:
    """Create a newsletter inside a channel.

    The alias is generated from the subject server-side. `files` becomes
    mandatory as soon as `addFile=1` is passed — it lives in that subpalette.
    """
    cmd = (
        f"contao:newsletter:create --subject={shlex.quote(subject)} "
        f"--pid={int(pid)} --no-interaction"
    )
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def newsletter_update(backend: ContaoBackend, newsletter_id: int, fields: dict) -> dict:
    """Update a newsletter.

    `sent` and `date` are refused server-side — see newsletter_send_refusal().
    """
    return run_update(backend, "contao:newsletter:update", newsletter_id, fields)


def newsletter_delete(backend: ContaoBackend, newsletter_id: int) -> dict:
    """Delete a newsletter. No cascade; recoverable from `undo restore`."""
    return run_delete(backend, "contao:newsletter:delete", newsletter_id)


# --- recipients -----------------------------------------------------------


def subscriber_create(backend: ContaoBackend, email: str, pid: int,
                      active: bool = False, fields: dict | None = None) -> dict:
    """Add a recipient to a channel.

    Mirrors Contao's own CSV import rather than the front end subscribe module:
    valid address, no duplicate in the channel, and not on the channel's deny
    list. `addedOn` stays empty, so the back end labels the row "added
    manually" instead of pretending it was an opt-in.

    `active` defaults to False. Double opt-in in Contao guards the front end
    self-subscription, not the table — but an operator adding addresses carries
    the consent themselves, so the active step is made explicit rather than
    assumed.
    """
    cmd = (
        f"contao:newsletter-recipient:create --email={shlex.quote(email)} "
        f"--pid={int(pid)} --no-interaction"
    )
    if active:
        cmd += " --active"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def subscriber_update(backend: ContaoBackend, recipient_id: int, fields: dict) -> dict:
    """Update a recipient. Deny list and address rules apply as on create."""
    return run_update(backend, "contao:newsletter-recipient:update", recipient_id, fields)


def subscriber_delete(backend: ContaoBackend, recipient_id: int) -> dict:
    """Remove a recipient from a channel.

    Deleting is not unsubscribing: no `tl_newsletter_deny_list` entry is
    written, so the same address can be added again tomorrow. For an actual
    opt-out use `--set active=0` or the back end's block action.
    """
    return run_delete(backend, "contao:newsletter-recipient:delete", recipient_id)


# --- the one thing this CLI will not do -----------------------------------


#: Why `newsletter send` refuses, in the words an agent gets.
#:
#: 🎯 The point of registering a command that always fails is that
#: "No such command 'send'" reads like a gap, and an agent that sees a gap
#: looks for a way around it. The nearest one is `UPDATE tl_newsletter SET
#: sent=1`, which sends nothing and publishes the newsletter in the front end
#: — strictly worse than doing nothing. So the message names that route and
#: rules it out, rather than leaving it to be discovered.
SEND_REFUSAL = (
    "`newsletter send` is not available in this CLI, by design — not a missing feature.\n"
    "\n"
    "Sending reaches real recipients and cannot be undone. Contao's own send routine is\n"
    "browser-driven: each cycle ends with a JavaScript timer that reloads the next batch,\n"
    "so it cannot run outside a back-end session at all.\n"
    "\n"
    "Do NOT work around this. Setting tl_newsletter.sent=1 directly does not send anything.\n"
    "It marks the newsletter as sent and publishes it in the front end archive, because the\n"
    "reader lists exactly the records with sent=1. That is worse than doing nothing, and\n"
    "contao-ai-core-bundle refuses writes to `sent` and `date` for that reason.\n"
    "\n"
    "A person sends the newsletter in the Contao back end:\n"
    "  Newsletters -> <channel> -> send icon"
)


def newsletter_send_refusal() -> str:
    """The refusal text for `newsletter send`. See SEND_REFUSAL."""
    return SEND_REFUSAL
