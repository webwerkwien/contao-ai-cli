"""
contao-ai-cli: Agent-native CLI for Contao 5 via SSH.

Wraps Contao's Symfony Console (php bin/console) with a Python CLI
that agents can use over SSH. The real Contao installation is a
hard dependency — this CLI does not reimplement Contao functionality.
"""
import click

from cli_anything.contao.cli.helpers import __version__
from cli_anything.contao.cli.cli_connect import connect, session_list, session_delete
from cli_anything.contao.cli.cli_cache import cache
from cli_anything.contao.cli.cli_contao import contao_group
from cli_anything.contao.cli.cli_user import user
from cli_anything.contao.cli.cli_member import member
from cli_anything.contao.cli.cli_page import page
from cli_anything.contao.cli.cli_layout import layout
from cli_anything.contao.cli.cli_article import article
from cli_anything.contao.cli.cli_content import content
from cli_anything.contao.cli.cli_faq import faq
from cli_anything.contao.cli.cli_newsletter import newsletter
from cli_anything.contao.cli.cli_news import news
from cli_anything.contao.cli.cli_event import event
from cli_anything.contao.cli.cli_comment import comment
from cli_anything.contao.cli.cli_listing import listing
from cli_anything.contao.cli.cli_version import version
from cli_anything.contao.cli.cli_file import file
from cli_anything.contao.cli.cli_template import template
from cli_anything.contao.cli.cli_form import form
from cli_anything.contao.cli.cli_backup import backup
from cli_anything.contao.cli.cli_debug import debug
from cli_anything.contao.cli.cli_messenger import messenger
from cli_anything.contao.cli.cli_mailer import mailer
from cli_anything.contao.cli.cli_security import security
from cli_anything.contao.cli.cli_search import search
from cli_anything.contao.cli.cli_schema import schema
from cli_anything.contao.cli.cli_repl import repl


# ─── Root group ───────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--session", default=None, help="Session file path")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, session, as_json):
    """contao-ai-cli — Agent-native CLI for Contao 5 via SSH.\n
    Connect to a Contao installation and run console commands remotely.
    Run without arguments to enter REPL mode.
    """
    ctx.ensure_object(dict)
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
cli.add_command(member)
cli.add_command(page)
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


if __name__ == "__main__":
    cli()
