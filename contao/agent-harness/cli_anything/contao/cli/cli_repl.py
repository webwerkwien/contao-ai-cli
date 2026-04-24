"""
repl command — Interactive REPL mode.
"""
import click

from cli_anything.contao.core import session as session_mod
from .helpers import skin


@click.command()
@click.pass_context
def repl(ctx):
    """Enter interactive REPL mode."""
    # Late import to avoid circular dependency (cli_repl → contao_cli → cli_repl)
    from cli_anything.contao.contao_cli import cli as root_cli

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
            args = line.split()
            ctx_standalone = root_cli.make_context("cli", args, parent=None,
                                                   obj={"session": ctx.obj.get("session"),
                                                        "as_json": False})
            with ctx_standalone:
                root_cli.invoke(ctx_standalone)
        except SystemExit:
            pass
        except Exception as e:
            skin.error(str(e))

    skin.print_goodbye()
