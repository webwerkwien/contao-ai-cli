"""
repl command — Interactive REPL mode.
"""
import click

from contao_ai_cli.core import session as session_mod
from .helpers import skin


@click.command()
@click.pass_context
def repl(ctx):
    """Enter interactive REPL mode."""
    # Late import to avoid circular dependency (cli_repl → contao_cli → cli_repl)
    from contao_ai_cli.contao_cli import cli as root_cli

    skin.print_banner()
    session_cfg = session_mod.load_session(ctx.obj.get("session"))
    if session_cfg:
        skin.info(f"Connected: {session_cfg.get('user')}@{session_cfg.get('host')} "
                  f"  {session_cfg.get('contao_root')}")
    else:
        skin.warning("No session. Run: contao-ai-cli connect --host HOST --user USER --root PATH")

    pt_session = skin.create_prompt_session()
    commands = {
        "connect": "Connect to a Contao installation",
        "cache clear": "Clear cache",
        "cache warmup": "Warm up cache",
        "contao migrate": "Run migrations",
        "contao maintenance enable|disable|status": "Manage maintenance mode",
        "contao filesync": "Sync file system",
        "contao cron": "Run cron jobs",
        "user list": "List backend users",
        "user create": "Create a user",
        "backup create": "Create backup",
        "backup list": "List backups",
        "backup restore NAME": "Restore a backup",
        "debug twig": "Show template hierarchy",
        "debug dca TABLE": "Dump DCA config",
        "debug pages": "Show page controllers",
        "messenger stats": "Message queue stats",
        "exit / quit": "Leave REPL",
    }

    while True:
        try:
            host = session_cfg.get("host", "?") if session_cfg else "?"
            line = skin.get_input(pt_session, project_name=host)
        except (EOFError, KeyboardInterrupt):
            break

        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            break
        if line in ("help", "?"):
            skin.help(commands)
            continue

        # Parse and invoke via click
        try:
            args = split_line(line)
        except ValueError as e:
            skin.error(f"Could not read the line: {e}")
            continue

        try:
            ctx_standalone = root_cli.make_context("cli", args, parent=None,
                                                   obj={"session": ctx.obj.get("session"),
                                                        "as_json": False})
            with ctx_standalone:
                root_cli.invoke(ctx_standalone)
        except SystemExit:
            pass
        except click.Abort:
            # A declined prompt ("delete …? no"). str(Abort()) is empty, so this
            # printed a bare red cross until v0.30.0.
            skin.warning("Aborted, nothing changed.")
        except click.ClickException as e:
            skin.error(e.format_message())
        except Exception as e:
            skin.error(str(e) or type(e).__name__)

    skin.print_goodbye()


def split_line(line: str) -> list[str]:
    """Split a REPL line the way a shell would, quotes included.

    Until v0.30.0 this was `line.split()`: `page create --title "Über uns"` became
    `--title '"Über'` plus a stray `uns"`, so any value with a space broke.

    POSIX rules, as on the command line the guide shows: a backslash escapes the
    next character. Contao paths use forward slashes, so that costs nothing there.

    :raises ValueError: on an unclosed quote
    """
    import shlex

    return shlex.split(line)
