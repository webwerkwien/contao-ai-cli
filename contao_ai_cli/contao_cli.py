"""
contao-ai-cli: Agent-native CLI for Contao 5 via SSH.

Wraps Contao's Symfony Console (php bin/console) with a Python CLI
that agents can use over SSH. The real Contao installation is a
hard dependency — this CLI does not reimplement Contao functionality.
"""
import json
import os
import sys

import click

from contao_ai_cli.cli import helpers as helpers_mod
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
from contao_ai_cli.cli.cli_self_update import self_update
from contao_ai_cli.cli.cli_bundle import bundle
from contao_ai_cli.cli.cli_guide import guide
from contao_ai_cli.core import update_notice


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

    # Update notice (v0.21.0): one stderr line on the first command after a pause,
    # after the command's own output. See core/update_notice.py.
    notice_session = session or session_mod.DEFAULT_SESSION_FILE
    subcommand = ctx.invoked_subcommand

    def _notice_unless_failed():
        # call_on_close runs while the command's own exception (if any) is still
        # in flight, so sys.exc_info() names it here (review 2026-09-17). A
        # failing command has nothing to say about whether the CLI or the
        # bundles are current.
        if update_notice.command_failed(sys.exc_info()[1]):
            return
        update_notice.after_command(notice_session, subcommand)

    ctx.call_on_close(_notice_unless_failed)

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
cli.add_command(self_update)
cli.add_command(bundle)
cli.add_command(guide)


# --- --set-file, attached wherever --set already is --------------------------

# Commands whose `--set` names the record that selects a palette rather than a
# value to write. Reading `type=unfiltered_html` from a file makes no sense, so
# they do not get `--set-file`. Listed by path so the exclusion is a decision
# with a reason, not an accident of how a module happens to parse its options;
# test_set_file.py fails if a command leaves this list without gaining the option.
SET_FILE_EXCLUDED = frozenset({"schema mandatory", "schema palette", "schema resolve"})


def attach_set_file_options(group, prefix: str = "") -> None:
    """
    Give every command that takes `--set` the matching `--set-file`.

    Done by walking the finished command tree rather than by writing the option
    into forty-nine decorators: a list maintained by hand drifts the moment
    someone adds a command, and the drift is silent -- the option simply is not
    there, and the caller reads that as "not supported here".

    Where `--set` was `required`, it stops being so: a caller who passes only
    `--set-file` has supplied a change, and Click checks `required` before any
    callback could say so. The demand does not disappear -- `set_option_callback`
    takes it over, and it sees both options.
    """
    ctx = click.Context(group)
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        path = f"{prefix}{name}"
        if isinstance(command, click.Group):
            attach_set_file_options(command, f"{path} ")
            continue
        opts = {o for p in command.params for o in getattr(p, "opts", [])}
        if "--set" not in opts or "--set-file" in opts or path in SET_FILE_EXCLUDED:
            continue
        for param in command.params:
            if "--set" not in getattr(param, "opts", []) or not param.required:
                continue
            if param.callback is not None:
                # Refuse rather than overwrite: a callback already there would
                # disappear without a sound, and this loop is its only reader.
                raise RuntimeError(
                    f"`{path}` already has a --set callback; attach_set_file_options would lose it"
                )
            param.required = False
            param.callback = helpers_mod.set_option_callback
        command.params.append(helpers_mod.set_file_option())


attach_set_file_options(cli)


def _json_requested(argv) -> bool:
    """True when `--json` appears among the arguments, before a `--` separator.

    The flag exists twice -- on the root group and on most commands -- and an
    error can happen before either has been parsed (a usage error) or after
    the command's context is gone (anything raised from inside it). The
    argument list is the one place that knows in both cases. A value that is
    literally `--json` (`--title --json`) would count as well; that is the
    price of reading tokens instead of parsed options, and it only changes the
    format of an error.
    """
    for token in argv:
        if token == "--":
            return False
        if token == "--json":
            return True
    return False


def _print_error(message: str, code: int, as_json: bool) -> None:
    """One error, in the form the caller asked for.

    Under `--json` the object goes to stdout, where the caller parses the
    answer, in the shape `connect` and `bundle` already used for their own
    failures: `{"status": "error", "code": N, "message": "..."}`. Without it,
    the familiar `Error: ...` line on stderr.
    """
    if as_json:
        click.echo(json.dumps({"status": "error", "code": code, "message": message},
                              ensure_ascii=False))
    else:
        click.echo(f"Error: {message}", err=True)


def main() -> None:
    """Entry point: errors in the requested format, and a report for defects.

    Click runs in non-standalone mode so that the errors it planned for reach
    this function instead of being printed inside Click: `ClickException` (and
    therefore `ContaoBackendError`) exits with its own code, `Abort` exits 1,
    `SystemExit` carries its own code, `ctx.exit(n)` comes back as the return
    value. Until v0.28.0 Click printed them itself, so `--json` had no say and
    an agent got `Error: ...` as plain text where the guide promised JSON.

    Whatever reaches the last handler got past all of that, which is very nearly
    the definition of a defect -- so the report is generated for what arrives
    there rather than for a list of failure types someone has to keep current.

    The one exception that is *not* automatically a defect is `BridgeError`: a
    4xx from the bridge is the server telling us something about the request
    (wrong token, missing route), and reporting those would train users to send
    noise. `is_reportable()` draws that line, and it is the same 500/422 line the
    bundles draw.

    The report goes to stderr and the exit code stays 1, with or without
    `--json`: stdout carries at most the one error object.
    """
    # Also done in the cli callback, but Click raises "No such command" and bad
    # root options before that callback runs -- and printing that error on a
    # cp1252 stdout crashed on the first character outside it (review v0.28.0:
    # `--json <emoji>` exited 1 with a traceback instead of 2 with the object).
    configure_output_encoding()
    as_json = _json_requested(sys.argv[1:])
    try:
        rv = cli(standalone_mode=False)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        # A user pressing Ctrl+C is not a defect and does not want a wall of text.
        raise SystemExit(130)
    except click.ClickException as exc:
        if as_json:
            _print_error(exc.format_message(), exc.exit_code, True)
        else:
            exc.show()
        raise SystemExit(exc.exit_code)
    except click.Abort:
        # A declined confirmation, or Ctrl+C at a prompt (Click converts it).
        if as_json:
            _print_error("Aborted!", 1, True)
        else:
            click.echo("Aborted!", err=True)
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001 -- the top-level net, by design
        from contao_ai_cli.utils import error_report

        _print_error(str(exc), 1, as_json)

        if error_report.is_reportable(exc):
            error_report.emit(exc, {"status": getattr(exc, "status", None)})

        raise SystemExit(1)

    # Non-standalone Click returns the code of `ctx.exit(n)` (and 0 for --help
    # and --version). No command returns a value of its own, so an int here is
    # always an exit code.
    if isinstance(rv, int) and not isinstance(rv, bool) and rv:
        raise SystemExit(rv)


if __name__ == "__main__":
    main()
