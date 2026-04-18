"""
cli-anything-contao: Agent-native CLI for Contao 5 via SSH.

Wraps Contao's Symfony Console (php bin/console) with a Python CLI
that agents can use over SSH. The real Contao installation is a
hard dependency — this CLI does not reimplement Contao functionality.
"""
import json
import os
import sys
import click

from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.utils.repl_skin import ReplSkin
from cli_anything.contao.core import (
    session as session_mod,
    cache as cache_mod,
    contao_ops,
    user as user_mod,
    backup as backup_mod,
    debug_ops,
    messenger as messenger_mod,
    dca_schema,
)

__version__ = "1.0.0"

skin = ReplSkin("contao", version=__version__)


def _get_backend(session_path=None):
    path = session_path or session_mod.DEFAULT_SESSION_FILE
    try:
        return ContaoBackend.from_session(path)
    except ContaoBackendError as e:
        click.echo(click.style(f"✗ {e}", fg="red"), err=True)
        sys.exit(1)


def _output(data, as_json=False):
    if as_json:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, dict) and "output" in data:
            click.echo(data["output"])
        elif isinstance(data, (list, dict)):
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            click.echo(str(data))


# ─── Root group ───────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--session", default=None, help="Session file path")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, session, as_json):
    """cli-anything-contao — Agent-native CLI for Contao 5 via SSH.\n
    Connect to a Contao installation and run console commands remotely.
    Run without arguments to enter REPL mode.
    """
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    ctx.obj["as_json"] = as_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ─── connect ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--host", required=True, help="SSH host")
@click.option("--user", required=True, help="SSH user")
@click.option("--root", required=True, help="Contao root path on server")
@click.option("--key", default=None, help="SSH private key path")
@click.option("--port", default=22, help="SSH port (default: 22)")
@click.option("--php", default="php", help="PHP binary (default: php)")
@click.option("--name", default=None, help="Session name (default: session)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def connect(ctx, host, user, root, key, port, php, name, as_json):
    """Connect to a Contao installation and save session config."""
    session_path = session_mod.get_session_path(name)
    config = {
        "host": host,
        "user": user,
        "contao_root": root,
        "key_path": key,
        "port": port,
        "php_path": php,
    }
    # Test connection
    try:
        backend = ContaoBackend(**{k: v for k, v in config.items() if v is not None})
        result = backend.run("--version")
        saved = session_mod.save_session(config, session_path)
        data = {"status": "connected", "session": saved, "version": result["stdout"]}
        _output(data, as_json or ctx.obj.get("as_json"))
    except ContaoBackendError as e:
        click.echo(click.style(f"✗ Connection failed: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command("session-list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def session_list(ctx, as_json):
    """List saved sessions."""
    sessions = session_mod.list_sessions()
    _output(sessions, as_json or ctx.obj.get("as_json"))


@cli.command("session-delete")
@click.option("--name", default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def session_delete(ctx, name, as_json):
    """Delete a session."""
    path = session_mod.get_session_path(name)
    session_mod.delete_session(path)
    _output({"status": "deleted", "path": path}, as_json or ctx.obj.get("as_json"))


# ─── cache group ──────────────────────────────────────────────────────────────

@cli.group()
def cache():
    """Cache management."""


@cache.command("clear")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_clear(ctx, as_json):
    """Clear the Contao/Symfony cache."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_clear(b), as_json or ctx.obj.get("as_json"))


@cache.command("warmup")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_warmup(ctx, as_json):
    """Warm up the cache."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_warmup(b), as_json or ctx.obj.get("as_json"))


@cache.command("pool-list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_pool_list(ctx, as_json):
    """List cache pools."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_pool_list(b), as_json or ctx.obj.get("as_json"))


@cache.command("pool-clear")
@click.argument("pool", default="cache.global_clearer")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cache_pool_clear(ctx, pool, as_json):
    """Clear a specific cache pool."""
    b = _get_backend(ctx.obj.get("session"))
    _output(cache_mod.cache_pool_clear(b, pool), as_json or ctx.obj.get("as_json"))


# ─── contao group ─────────────────────────────────────────────────────────────

@cli.group("contao")
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


# ─── user group ───────────────────────────────────────────────────────────────

@cli.group()
def user():
    """Backend user management."""


@user.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_list(ctx, as_json):
    """List backend users."""
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_list(b), as_json or ctx.obj.get("as_json"))


@user.command("create")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--name", required=True, help="Full name (required by Contao)")
@click.option("--email", required=True, help="E-mail address (required by Contao)")
@click.option("--language", default="en", show_default=True,
              help="Back end language, e.g. de, en (required by Contao)")
@click.option("--admin", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_create(ctx, username, password, name, email, language, admin, as_json):
    """Create a backend user."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE

    # DCA validation — runs only if schema has been synced, skipped otherwise
    missing = dca_schema.validate_fields(
        table='tl_user',
        provided={'username': username, 'password': password,
                  'name': name, 'email': email, 'language': language},
        session_path=session_path,
    )
    if missing:
        schema = dca_schema.load_schema('tl_user', session_path)
        details = []
        for f in missing:
            fdef = schema['fields'].get(f, {})
            label = fdef.get('label') or f
            details.append(f"--{f} ({label})")
        raise click.UsageError(
            f"Missing mandatory field(s) for tl_user: {', '.join(details)}\n"
            f"Run 'schema sync tl_user' to refresh the field list."
        )

    b = _get_backend(session_path)
    _output(user_mod.user_create(b, username, password, name, email, language, admin),
            as_json or ctx.obj.get("as_json"))


@user.command("password")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_password(ctx, username, password, as_json):
    """Change a user's password."""
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_password(b, username, password),
            as_json or ctx.obj.get("as_json"))


# ─── backup group ─────────────────────────────────────────────────────────────

@cli.group()
def backup():
    """Database backup management."""


@backup.command("create")
@click.argument("name", default="")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def backup_create(ctx, name, as_json):
    """Create a database backup."""
    b = _get_backend(ctx.obj.get("session"))
    _output(backup_mod.backup_create(b, name), as_json or ctx.obj.get("as_json"))


@backup.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def backup_list(ctx, as_json):
    """List existing backups."""
    b = _get_backend(ctx.obj.get("session"))
    _output(backup_mod.backup_list(b), as_json or ctx.obj.get("as_json"))


@backup.command("restore")
@click.argument("backup_name")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def backup_restore(ctx, backup_name, as_json):
    """Restore a database backup."""
    b = _get_backend(ctx.obj.get("session"))
    _output(backup_mod.backup_restore(b, backup_name), as_json or ctx.obj.get("as_json"))


# ─── debug group ──────────────────────────────────────────────────────────────

@cli.group()
def debug():
    """Debug and inspection tools."""


@debug.command("twig")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_twig(ctx, as_json):
    """Display Contao template hierarchy."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_contao_twig(b), as_json or ctx.obj.get("as_json"))


@debug.command("dca")
@click.argument("table")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_dca(ctx, table, as_json):
    """Dump DCA configuration for a table."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_dca(b, table), as_json or ctx.obj.get("as_json"))


@debug.command("pages")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_pages(ctx, as_json):
    """Display page controller configuration."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_pages(b), as_json or ctx.obj.get("as_json"))


@debug.command("plugins")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_plugins(ctx, as_json):
    """Display Contao Manager plugin configurations."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_plugins(b), as_json or ctx.obj.get("as_json"))


@debug.command("router")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_router(ctx, as_json):
    """Display current routes."""
    b = _get_backend(ctx.obj.get("session"))
    _output(debug_ops.debug_router(b), as_json or ctx.obj.get("as_json"))


# ─── messenger group ──────────────────────────────────────────────────────────

@cli.group()
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


# ─── SCHEMA ──────────────────────────────────────────────────────────────────

@cli.group()
def schema():
    """DCA schema sync — fetch field definitions from the live server."""
    pass


@schema.command("sync")
@click.argument("table", default="")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_sync(ctx, table, as_json):
    """Sync DCA schema for TABLE (or all default tables if omitted).

    Fetches field definitions from the live server and stores them locally
    so CLI commands can validate against the project's actual DCA config.

    Default tables: tl_user, tl_page, tl_article, tl_content, tl_member
    """
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    if table:
        result = dca_schema.sync_table(b, table, session_path)
        fields = result["fields"]
        mandatory = [f for f, d in fields.items() if d.get("mandatory")]
        summary = {
            "table": table,
            "fetched": result["fetched"],
            "total_fields": len(fields),
            "mandatory_fields": mandatory,
        }
        _output(summary, as_json or ctx.obj.get("as_json"))
    else:
        results = dca_schema.sync_all(b, session_path)
        summary = {}
        for tbl, res in results.items():
            if "error" in res:
                summary[tbl] = {"status": "error", "message": res["error"]}
            else:
                mandatory = [f for f, d in res["fields"].items() if d.get("mandatory")]
                summary[tbl] = {
                    "status": "ok",
                    "total_fields": len(res["fields"]),
                    "mandatory_fields": mandatory,
                }
        _output(summary, as_json or ctx.obj.get("as_json"))


@schema.command("show")
@click.argument("table")
@click.option("--mandatory-only", is_flag=True, help="Show only mandatory fields")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_show(ctx, table, mandatory_only, as_json):
    """Show cached DCA schema for TABLE."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    rows = dca_schema.field_summary(table, session_path)
    if not rows:
        raise click.ClickException(
            f"No schema for '{table}'. Run: schema sync {table}"
        )
    if mandatory_only:
        rows = [r for r in rows if r["mandatory"]]
    _output(rows, as_json or ctx.obj.get("as_json"))


@schema.command("mandatory")
@click.argument("table")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_mandatory(ctx, table, as_json):
    """List mandatory fields for TABLE."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    fields = dca_schema.mandatory_fields(table, session_path)
    if not fields:
        schema = dca_schema.load_schema(table, session_path)
        if schema is None:
            raise click.ClickException(
                f"No schema for '{table}'. Run: schema sync {table}"
            )
    _output({"table": table, "mandatory": fields}, as_json or ctx.obj.get("as_json"))


# ─── REPL ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def repl(ctx):
    """Enter interactive REPL mode."""
    skin.print_banner()
    session_cfg = session_mod.load_session(ctx.obj.get("session"))
    if session_cfg:
        skin.info(f"Connected: {session_cfg.get('user')}@{session_cfg.get('host')} "
                  f"→ {session_cfg.get('contao_root')}")
    else:
        skin.warning("No session. Run: cli-anything-contao connect --host HOST --user USER --root PATH")

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
            ctx_standalone = cli.make_context("cli", args, parent=None,
                                              obj={"session": ctx.obj.get("session"),
                                                   "as_json": False})
            with ctx_standalone:
                cli.invoke(ctx_standalone)
        except SystemExit:
            pass
        except Exception as e:
            skin.error(str(e))

    skin.print_goodbye()


if __name__ == "__main__":
    cli()
