"""
contao-ai-cli: Agent-native CLI for Contao 5 via SSH.

Wraps Contao's Symfony Console (php bin/console) with a Python CLI
that agents can use over SSH. The real Contao installation is a
hard dependency — this CLI does not reimplement Contao functionality.
"""
import os

import click

from contao_ai_cli.cli.helpers import __version__, configure_output_encoding
from contao_ai_cli.core import session as session_mod
from contao_ai_cli.cli.cli_connect import connect, session_list, session_delete
from contao_ai_cli.cli.cli_cache import cache
from contao_ai_cli.cli.cli_contao import contao_group
from contao_ai_cli.cli.cli_user import user
from contao_ai_cli.cli.cli_user_group import user_group
from contao_ai_cli.cli.cli_member import member
from contao_ai_cli.cli.cli_member_group import member_group
from contao_ai_cli.cli.cli_page import page
from contao_ai_cli.cli.cli_record import record
from contao_ai_cli.cli.cli_image_size import image_size
from contao_ai_cli.cli.cli_theme import theme
from contao_ai_cli.cli.cli_undo import undo
from contao_ai_cli.cli.cli_settings import settings
from contao_ai_cli.cli.cli_module import module
from contao_ai_cli.cli.cli_layout import layout
from contao_ai_cli.cli.cli_article import article
from contao_ai_cli.cli.cli_content import content
from contao_ai_cli.cli.cli_faq import faq
from contao_ai_cli.cli.cli_newsletter import newsletter
from contao_ai_cli.cli.cli_news import news
from contao_ai_cli.cli.cli_event import event
from contao_ai_cli.cli.cli_comment import comment
from contao_ai_cli.cli.cli_listing import listing
from contao_ai_cli.cli.cli_version import version
from contao_ai_cli.cli.cli_file import file
from contao_ai_cli.cli.cli_template import template
from contao_ai_cli.cli.cli_form import form
from contao_ai_cli.cli.cli_backup import backup
from contao_ai_cli.cli.cli_debug import debug
from contao_ai_cli.cli.cli_messenger import messenger
from contao_ai_cli.cli.cli_mailer import mailer
from contao_ai_cli.cli.cli_security import security
from contao_ai_cli.cli.cli_search import search
from contao_ai_cli.cli.cli_schema import schema
from contao_ai_cli.cli.cli_repl import repl
from contao_ai_cli.cli.cli_bridge import bridge
from contao_ai_cli.cli.cli_ext import ext
from contao_ai_cli.cli.cli_health import health


# ─── Root group ───────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--session", default=None, help="Session name (e.g. 'c5-axeltest') or full path to a session.json file")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, session, as_json):
    """contao-ai-cli — Agent-native CLI for Contao 5 via SSH.\n
    Connect to a Contao installation and run console commands remotely.
    Run without arguments to enter REPL mode.
    """
    # Before any command can print a record: a cp1252 stdout turns the first
    # umlaut coming back from the server into a UnicodeEncodeError. See
    # configure_output_encoding() for why this sits here and not at each call site.
    configure_output_encoding()

    ctx.ensure_object(dict)
    # Accept --session as either a bare session name (resolved against the
    # default session dir) OR a full path to a *.json file. Without this,
    # `--session c5-axeltest` was interpreted as a literal relative path
    # and resolved to a non-existent file.
    if session and not session.endswith(".json") and os.sep not in session and "/" not in session:
        session = session_mod.get_session_path(session)
    ctx.obj["session"] = session
    ctx.obj["as_json"] = as_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ─── Register all sub-groups and standalone commands ─────────────────────────

cli.add_command(connect)
cli.add_command(session_list)
cli.add_command(session_delete)
cli.add_command(repl)
cli.add_command(cache)
cli.add_command(contao_group)
cli.add_command(user)
cli.add_command(user_group)
cli.add_command(member)
cli.add_command(member_group)
cli.add_command(page)
cli.add_command(record)
cli.add_command(image_size)
cli.add_command(theme)
cli.add_command(module)
cli.add_command(layout)
cli.add_command(article)
cli.add_command(content)
cli.add_command(faq)
cli.add_command(newsletter)
cli.add_command(news)
cli.add_command(event)
cli.add_command(comment)
cli.add_command(listing)
cli.add_command(version)
cli.add_command(undo)
cli.add_command(settings)
cli.add_command(file)
cli.add_command(template)
cli.add_command(form)
cli.add_command(backup)
cli.add_command(debug)
cli.add_command(messenger)
cli.add_command(mailer)
cli.add_command(security)
cli.add_command(search)
cli.add_command(schema)
cli.add_command(bridge)
cli.add_command(ext)
cli.add_command(health)


def main() -> None:
    """Entry point that attaches an error report to unexpected failures.

    Click already handles everything it planned for: `ClickException` (and
    therefore `ContaoBackendError`) prints one `Error: ...` line and exits 1,
    `Abort` exits 1 quietly, `SystemExit` carries its own code. Whatever reaches
    the handler below got past all of that, which is very nearly the definition
    of a defect -- so the report is generated for what arrives here rather than
    for a list of failure types someone has to keep current.

    The one exception that is *not* automatically a defect is `BridgeError`: a
    4xx from the bridge is the server telling us something about the request
    (wrong token, missing route), and reporting those would train users to send
    noise. `is_reportable()` draws that line, and it is the same 500/422 line the
    bundles draw.

    The report goes to stderr and the exit code stays 1: nothing about how this
    CLI fails changes, there is now simply something usable underneath it.
    """
    try:
        cli()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        # A user pressing Ctrl+C is not a defect and does not want a wall of text.
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 -- the top-level net, by design
        from contao_ai_cli.utils import error_report

        click.echo(f"Error: {exc}", err=True)

        if error_report.is_reportable(exc):
            error_report.emit(exc, {"status": getattr(exc, "status", None)})

        raise SystemExit(1)


if __name__ == "__main__":
    main()
