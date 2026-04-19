"""
contao-cli-agent: Agent-native CLI for Contao 5 via SSH.

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
    member as member_mod,
    page as page_mod,
    article as article_mod,
    content as content_mod,
    faq as faq_mod,
    newsletter as newsletter_mod,
    news as news_mod,
    event as event_mod,
    comment as comment_mod,
    listing as listing_mod,
    file as file_mod,
    form as form_mod,
    backup as backup_mod,
    debug_ops,
    messenger as messenger_mod,
    mailer as mailer_mod,
    security as security_mod,
    search as search_mod,
    dca_schema,
)

__version__ = "1.0.0"

skin = ReplSkin("contao", version=__version__)


def _get_backend(session_path=None):
    path = session_path or session_mod.DEFAULT_SESSION_FILE
    try:
        return ContaoBackend.from_session(path)
    except ContaoBackendError as e:
        click.echo(click.style(f"[ERROR] {e}", fg="red"), err=True)
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


def _detect_bridge(backend) -> bool:
    """Check if contao-cli-bridge commands are available on the server."""
    try:
        result = backend.run("list")
        return "contao:user:update" in result["stdout"]
    except Exception:
        return False


def _require_bridge(ctx, command_name: str):
    """Raise UsageError with install hint if bridge is not available."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    try:
        with open(session_path) as f:
            cfg = json.load(f)
        bridge_available = cfg.get("bridge_available", False)
    except Exception:
        bridge_available = False
    if not bridge_available:
        raise click.UsageError(
            f"'{command_name}' requires contao-cli-bridge which is not installed on this server.\n"
            f"Install with: composer require webwerkwien/contao-cli-bridge"
        )


# ─── Root group ───────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--session", default=None, help="Session file path")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, session, as_json):
    """contao-cli-agent — Agent-native CLI for Contao 5 via SSH.\n
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
    click.echo(click.style(
        "\n[!] Warning: contao-cli-agent can irreversibly modify or delete data on the target server.\n"
        "   Always ensure you have a current backup before proceeding.\n",
        fg="yellow"
    ))
    click.confirm("I understand and have a backup. Continue?", abort=True)

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

        if click.confirm("Create a database backup now?", default=True):
            click.echo("Creating backup...")
            backup_result = backup_mod.backup_create(backend)
            click.echo(click.style(f"[OK] Backup created.", fg="green"))
            if backup_result.get("output"):
                click.echo(backup_result["output"].strip())

    except ContaoBackendError as e:
        click.echo(click.style(f"[ERROR] Connection failed: {e}", fg="red"), err=True)
        sys.exit(1)

    b = ContaoBackend.from_session(session_path)
    bridge = _detect_bridge(b)
    with open(session_path) as f:
        cfg = json.load(f)
    cfg["bridge_available"] = bridge
    with open(session_path, "w") as f:
        json.dump(cfg, f, indent=2)

    if bridge:
        click.echo("Bridge: available (full CRUD support enabled)")
    else:
        click.echo("Bridge: not installed — contao-cli-bridge enables CRUD operations (update, delete, create).")
        # TODO: Implement automatic bridge installation via composer require.
        #       Requires either a public Composer repository or a configured GitHub
        #       auth token on the server (~/.composer/auth.json).
        #       Until then, manual install: composer require webwerkwien/contao-cli-bridge
        if click.confirm("Install contao-cli-bridge now?", default=False):
            click.echo("Feature not yet available — please install manually:")
            click.echo("  composer require webwerkwien/contao-cli-bridge")


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


@user.command("update")
@click.argument("username")
@click.option("--field", "fields", multiple=True,
              metavar="FIELD=VALUE", help="Field to update, e.g. --field email=new@example.com")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_update(ctx, username, fields, as_json):
    """Update a backend user field via contao-cli-bridge."""
    _require_bridge(ctx, "user update")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_update(b, username, parsed), as_json or ctx.obj.get("as_json"))


@user.command("delete")
@click.argument("username")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def user_delete(ctx, username, as_json):
    """Delete a backend user via contao-cli-bridge."""
    _require_bridge(ctx, "user delete")
    b = _get_backend(ctx.obj.get("session"))
    _output(user_mod.user_delete(b, username), as_json or ctx.obj.get("as_json"))


# ─── member group ─────────────────────────────────────────────────────────────

@cli.group()
def member():
    """Manage Contao frontend members (tl_member)."""
    pass


@member.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_list_cmd(ctx, as_json):
    """List all frontend members."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(member_mod.member_list(b), as_json or ctx.obj.get("as_json"))


@member.command("create")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--firstname", required=True)
@click.option("--lastname", required=True)
@click.option("--email", required=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_create_cmd(ctx, username, password, firstname, lastname, email, as_json):
    """Create a new frontend member."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    missing = dca_schema.validate_fields(
        'tl_member',
        {'username': username, 'password': password,
         'firstname': firstname, 'lastname': lastname, 'email': email},
        session_path
    )
    if missing:
        schema = dca_schema.load_schema('tl_member', session_path)
        if schema:
            details = [f"--{f} ({schema['fields'][f].get('label') or f})" for f in missing]
        else:
            details = [f"--{f}" for f in missing]
        raise click.UsageError(f"Missing mandatory field(s) for tl_member: {', '.join(details)}")
    b = _get_backend(session_path)
    _output(member_mod.member_create(b, username, password, firstname, lastname, email),
            as_json or ctx.obj.get("as_json"))


@member.command("update")
@click.argument("username")
@click.option("--field", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_update(ctx, username, fields, as_json):
    """Update a frontend member field via contao-cli-bridge."""
    _require_bridge(ctx, "member update")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(member_mod.member_update(b, username, parsed), as_json or ctx.obj.get("as_json"))


@member.command("delete")
@click.argument("username")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def member_delete(ctx, username, as_json):
    """Delete a frontend member via contao-cli-bridge."""
    _require_bridge(ctx, "member delete")
    b = _get_backend(ctx.obj.get("session"))
    _output(member_mod.member_delete(b, username), as_json or ctx.obj.get("as_json"))


# ─── page group ───────────────────────────────────────────────────────────────

@cli.group()
def page():
    """Manage Contao pages (tl_page)."""
    pass


@page.command("list")
@click.option("--pid", type=int, default=None, help="Filter by parent page ID")
@click.pass_context
def page_list_cmd(ctx, pid):
    """List pages, optionally filtered by parent ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(page_mod.page_list(b, pid), ctx.obj.get("as_json"))


@page.command("tree")
@click.pass_context
def page_tree_cmd(ctx):
    """Show page tree (nested structure)."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(page_mod.page_tree(b), ctx.obj.get("as_json"))


@page.command("create")
@click.option("--title", required=True, help="Page title")
@click.option("--pid", type=int, default=0, show_default=True, help="Parent page ID")
@click.option("--type", "page_type", default="regular", show_default=True, help="Page type (regular, root, …)")
@click.option("--alias", default="", help="Page alias (auto-generated if omitted)")
@click.option("--language", default="de", show_default=True, help="Page language")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE", help="Extra fields, e.g. --set robots=noindex")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_create_cmd(ctx, title, pid, page_type, alias, language, fields, as_json):
    """Create a page via contao-cli-bridge."""
    _require_bridge(ctx, "page create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(page_mod.page_create(b, title, pid, page_type, alias, language, parsed),
            as_json or ctx.obj.get("as_json"))


# ─── article group ────────────────────────────────────────────────────────────

@cli.group()
def article():
    """Manage Contao articles (tl_article)."""
    pass


@article.command("list")
@click.option("--page", "page_id", type=int, default=None,
              help="Filter by page ID (pid)")
@click.pass_context
def article_list_cmd(ctx, page_id):
    """List articles, optionally filtered by page ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(article_mod.article_list(b, page_id), ctx.obj.get("as_json"))


@article.command("create")
@click.option("--title", required=True, help="Article title")
@click.option("--pid", type=int, required=True, help="Parent page ID")
@click.option("--column", "in_column", default="main", show_default=True, help="Layout column")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def article_create_cmd(ctx, title, pid, in_column, fields, as_json):
    """Create an article via contao-cli-bridge."""
    _require_bridge(ctx, "article create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(article_mod.article_create(b, title, pid, in_column, parsed),
            as_json or ctx.obj.get("as_json"))


# ─── content group ────────────────────────────────────────────────────────────

@cli.group()
def content():
    """Manage Contao content elements (tl_content)."""
    pass


@content.command("list")
@click.option("--article", "article_id", type=int, default=None,
              help="Filter by article ID (pid)")
@click.pass_context
def content_list_cmd(ctx, article_id):
    """List content elements, optionally filtered by article ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(content_mod.content_list(b, article_id), ctx.obj.get("as_json"))


@content.command("create")
@click.option("--type", "el_type", required=True, help="Element type (text, headline, image, …)")
@click.option("--pid", type=int, required=True, help="Parent ID (article ID)")
@click.option("--ptable", default="tl_article", show_default=True, help="Parent table")
@click.option("--text", default=None, help="Shortcut for --set text=VALUE")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def content_create_cmd(ctx, el_type, pid, ptable, text, fields, as_json):
    """Create a content element via contao-cli-bridge."""
    _require_bridge(ctx, "content create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    if text is not None:
        parsed.setdefault("text", text)
    b = _get_backend(ctx.obj.get("session"))
    _output(content_mod.content_create(b, el_type, pid, ptable, parsed),
            as_json or ctx.obj.get("as_json"))


# ─── faq group ────────────────────────────────────────────────────────────────

@cli.group()
def faq():
    """Manage Contao FAQ entries (tl_faq)."""
    pass


@faq.command("categories")
@click.pass_context
def faq_categories(ctx):
    """List all FAQ categories."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(faq_mod.faq_category_list(b), ctx.obj.get("as_json"))


@faq.command("list")
@click.option("--category", "category_id", type=int, default=None,
              help="Filter by category ID")
@click.pass_context
def faq_list_cmd(ctx, category_id):
    """List FAQ entries, optionally filtered by category ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(faq_mod.faq_list(b, category_id), ctx.obj.get("as_json"))


@faq.command("create")
@click.option("--question", required=True, help="FAQ question")
@click.option("--pid", type=int, required=True, help="FAQ category ID")
@click.option("--answer", default="", help="FAQ answer (HTML)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def faq_create_cmd(ctx, question, pid, answer, fields, as_json):
    """Create a FAQ entry via contao-cli-bridge."""
    _require_bridge(ctx, "faq create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(faq_mod.faq_create(b, question, pid, answer, parsed),
            as_json or ctx.obj.get("as_json"))


# ─── newsletter group ─────────────────────────────────────────────────────────

@cli.group()
def newsletter():
    """Manage Contao newsletters (tl_newsletter)."""
    pass


@newsletter.command("channels")
@click.pass_context
def newsletter_channels(ctx):
    """List all newsletter channels."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.channel_list(b), ctx.obj.get("as_json"))


@newsletter.command("list")
@click.option("--channel", "channel_id", type=int, default=None,
              help="Filter by channel ID")
@click.pass_context
def newsletter_list_cmd(ctx, channel_id):
    """List newsletters, optionally filtered by channel ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.newsletter_list(b, channel_id), ctx.obj.get("as_json"))


@newsletter.command("subscribers")
@click.option("--channel", "channel_id", type=int, default=None,
              help="Filter by channel ID")
@click.pass_context
def newsletter_subscribers(ctx, channel_id):
    """List newsletter subscribers."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(newsletter_mod.subscriber_list(b, channel_id), ctx.obj.get("as_json"))


# ─── news group ───────────────────────────────────────────────────────────────

@cli.group()
def news():
    """Manage Contao news entries (tl_news)."""
    pass


@news.command("archives")
@click.pass_context
def news_archives(ctx):
    """List all news archives."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(news_mod.news_archive_list(b), ctx.obj.get("as_json"))


@news.command("list")
@click.option("--archive", "archive_id", type=int, default=None,
              help="Filter by archive ID")
@click.pass_context
def news_list_cmd(ctx, archive_id):
    """List news entries, optionally filtered by archive ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(news_mod.news_list(b, archive_id), ctx.obj.get("as_json"))


@news.command("create")
@click.option("--headline", required=True, help="News headline")
@click.option("--pid", type=int, required=True, help="News archive ID")
@click.option("--date", default=None, help="Publication date (YYYY-MM-DD, default: today)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def news_create_cmd(ctx, headline, pid, date, fields, as_json):
    """Create a news entry via contao-cli-bridge."""
    _require_bridge(ctx, "news create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(news_mod.news_create(b, headline, pid, date, parsed),
            as_json or ctx.obj.get("as_json"))


# ─── event group ──────────────────────────────────────────────────────────────

@cli.group()
def event():
    """Manage Contao calendar events (tl_calendar_events)."""
    pass


@event.command("calendars")
@click.pass_context
def event_calendars(ctx):
    """List all calendars."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(event_mod.calendar_list(b), ctx.obj.get("as_json"))


@event.command("list")
@click.option("--calendar", "calendar_id", type=int, default=None,
              help="Filter by calendar ID")
@click.pass_context
def event_list_cmd(ctx, calendar_id):
    """List calendar events, optionally filtered by calendar ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(event_mod.event_list(b, calendar_id), ctx.obj.get("as_json"))


@event.command("create")
@click.option("--title", required=True, help="Event title")
@click.option("--pid", type=int, required=True, help="Calendar ID")
@click.option("--start-date", "start_date", default=None, help="Start date (YYYY-MM-DD, default: today)")
@click.option("--end-date", "end_date", default=None, help="End date (YYYY-MM-DD, default: start date)")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def event_create_cmd(ctx, title, pid, start_date, end_date, fields, as_json):
    """Create a calendar event via contao-cli-bridge."""
    _require_bridge(ctx, "event create")
    parsed = dict(f.split("=", 1) for f in fields if "=" in f)
    b = _get_backend(ctx.obj.get("session"))
    _output(event_mod.event_create(b, title, pid, start_date, end_date, parsed),
            as_json or ctx.obj.get("as_json"))


# ─── comment group ────────────────────────────────────────────────────────────

@cli.group()
def comment():
    """Manage Contao comments (tl_comments)."""
    pass


@comment.command("list")
@click.option("--source", default=None,
              help="Filter by source table (e.g. tl_news, tl_page)")
@click.option("--parent", "parent_id", type=int, default=None,
              help="Filter by parent record ID")
@click.pass_context
def comment_list_cmd(ctx, source, parent_id):
    """List comments, optionally filtered by source and/or parent ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(comment_mod.comment_list(b, source, parent_id), ctx.obj.get("as_json"))


# ─── listing group ────────────────────────────────────────────────────────────

@cli.group()
def listing():
    """Manage Contao listing modules (contao/listing-bundle)."""
    pass


@listing.command("modules")
@click.pass_context
def listing_modules(ctx):
    """List all configured listing modules."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(listing_mod.listing_module_list(b), ctx.obj.get("as_json"))


@listing.command("data")
@click.argument("module_id", type=int)
@click.pass_context
def listing_data_cmd(ctx, module_id):
    """Fetch listing data for a specific module ID."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(listing_mod.listing_data(b, module_id), ctx.obj.get("as_json"))


# ─── file group ───────────────────────────────────────────────────────────────

@cli.group()
def file():
    """Manage Contao files (DBAFS / tl_files)."""
    pass


@file.command("list")
@click.option("--path", default=None, help="Filter by path prefix (e.g. files/images)")
@click.option("--type", "type_filter", type=click.Choice(["file", "folder"]), default=None,
              help="Show only files or only folders")
@click.pass_context
def file_list_cmd(ctx, path, type_filter):
    """List files and folders from the Contao file manager."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(file_mod.file_list(b, path, type_filter), ctx.obj.get("as_json"))


@file.command("sync")
@click.pass_context
def file_sync_cmd(ctx):
    """Synchronize the DBAFS with the virtual filesystem (contao:filesync)."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(file_mod.file_sync(b), ctx.obj.get("as_json"))


@file.command("folder-create")
@click.option("--path", required=True, help="Folder path relative to Contao root, e.g. files/images/gallery")
@click.option("--public", "is_public", is_flag=True, help="Mark folder as publicly accessible")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_folder_create_cmd(ctx, path, is_public, as_json):
    """Create a folder in the Contao file system via contao-cli-bridge."""
    _require_bridge(ctx, "file folder-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.folder_create(b, path, is_public), as_json or ctx.obj.get("as_json"))


@file.command("process")
@click.option("--path", required=True, help="File path relative to Contao root, e.g. files/images/photo.jpg")
@click.option("--allowed-types", default="", help="Comma-separated allowed extensions (overrides Contao config)")
@click.option("--max-width",  type=int, default=0, help="Max image width in pixels (0 = use Contao config)")
@click.option("--max-height", type=int, default=0, help="Max image height in pixels (0 = use Contao config)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_process_cmd(ctx, path, allowed_types, max_width, max_height, as_json):
    """Validate and optionally resize a file already on the server via contao-cli-bridge."""
    _require_bridge(ctx, "file process")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_process(b, path, allowed_types, max_width, max_height),
            as_json or ctx.obj.get("as_json"))


@file.command("meta")
@click.option("--path", required=True, help="File or folder path relative to Contao root")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Metadata field to update, e.g. --set alt=Landschaft --set title=Bergblick")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_meta_cmd(ctx, path, fields, as_json):
    """Update metadata fields on a tl_files record via contao-cli-bridge."""
    _require_bridge(ctx, "file meta")
    invalid = [f for f in fields if "=" not in f]
    if invalid:
        raise click.UsageError(f"Invalid --set value(s): {invalid!r}. Expected format: FIELD=VALUE")
    parsed = dict(f.split("=", 1) for f in fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_meta_update(b, path, parsed), as_json or ctx.obj.get("as_json"))


# ─── form group ───────────────────────────────────────────────────────────────

@cli.group()
def form():
    """Manage Contao forms (tl_form / tl_form_field)."""
    pass


@form.command("list")
@click.pass_context
def form_list_cmd(ctx):
    """List all forms."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(form_mod.form_list(b), ctx.obj.get("as_json"))


@form.command("fields")
@click.argument("form_id", type=int)
@click.pass_context
def form_fields_cmd(ctx, form_id):
    """List all fields of a form (form_id = ID from tl_form)."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(form_mod.form_fields(b, form_id), ctx.obj.get("as_json"))


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


@debug.command("match")
@click.argument("path_info")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def debug_match(ctx, path_info, as_json):
    """Match a URL path to its Symfony route."""
    b = _get_backend(ctx.obj.get("session"))
    result = b.run(f"router:match {path_info}")
    _output({"output": result["stdout"]}, as_json or ctx.obj.get("as_json"))


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


# ─── mailer group ─────────────────────────────────────────────────────────────

@cli.group()
def mailer():
    """Mailer operations."""


@mailer.command("test")
@click.option("--to", required=True, help="Recipient e-mail address")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def mailer_test(ctx, to, as_json):
    """Send a test e-mail to verify mailer configuration."""
    b = _get_backend(ctx.obj.get("session"))
    _output(mailer_mod.mailer_test(b, to), as_json or ctx.obj.get("as_json"))


# ─── security group ───────────────────────────────────────────────────────────

@cli.group()
def security():
    """Security utilities."""


@security.command("hash-password")
@click.argument("password")
@click.option("--algorithm", default="auto", show_default=True,
              help="Hashing algorithm (auto, bcrypt, argon2i, argon2id, sodium)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def security_hash_password(ctx, password, algorithm, as_json):
    """Hash a password using Symfony's password hasher."""
    b = _get_backend(ctx.obj.get("session"))
    _output(security_mod.hash_password(b, password, algorithm),
            as_json or ctx.obj.get("as_json"))


# ─── search group ─────────────────────────────────────────────────────────────

@cli.group()
def search():
    """Search index management (cmsig/seal)."""


@search.command("reindex")
@click.option("--index", default="", help="Specific index name (all if omitted)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_reindex(ctx, index, as_json):
    """Rebuild the search index."""
    b = _get_backend(ctx.obj.get("session"))
    _output(search_mod.search_reindex(b, index), as_json or ctx.obj.get("as_json"))


@search.command("index-create")
@click.option("--index", default="", help="Specific index name (all if omitted)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_index_create(ctx, index, as_json):
    """Create search index."""
    b = _get_backend(ctx.obj.get("session"))
    _output(search_mod.search_index_create(b, index), as_json or ctx.obj.get("as_json"))


@search.command("index-drop")
@click.option("--index", default="", help="Specific index name (all if omitted)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def search_index_drop(ctx, index, as_json):
    """Drop search index."""
    b = _get_backend(ctx.obj.get("session"))
    _output(search_mod.search_index_drop(b, index), as_json or ctx.obj.get("as_json"))


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


@schema.command("resolve")
@click.argument("table", default="")
@click.argument("field", default="")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def schema_resolve(ctx, table, field, as_json):
    """Resolve __callback__ options in cached schemas.

    With TABLE: resolves all __callback__ fields in that table.
    With TABLE FIELD: resolves only that specific field.
    Without arguments: resolves all synced tables.

    Updates the local schema cache in-place.
    """
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)

    if table:
        try:
            results = dca_schema.resolve_callback_options(b, table, session_path,
                                                          field or None)
        except ValueError as e:
            raise click.ClickException(str(e))
        _output({table: results}, as_json or ctx.obj.get("as_json"))
    else:
        # Resolve all synced tables
        schema_dir = dca_schema._schema_dir(session_path)
        if not os.path.isdir(schema_dir):
            raise click.ClickException("No schemas synced yet. Run: schema sync")
        import glob as _glob
        tables = [
            os.path.splitext(os.path.basename(p))[0]
            for p in _glob.glob(os.path.join(schema_dir, '*.json'))
        ]
        all_results = {}
        for tbl in sorted(tables):
            try:
                res = dca_schema.resolve_callback_options(b, tbl, session_path)
                if res:
                    all_results[tbl] = res
            except Exception as e:
                all_results[tbl] = {'error': str(e)}
        _output(all_results, as_json or ctx.obj.get("as_json"))


# ─── REPL ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def repl(ctx):
    """Enter interactive REPL mode."""
    skin.print_banner()
    session_cfg = session_mod.load_session(ctx.obj.get("session"))
    if session_cfg:
        skin.info(f"Connected: {session_cfg.get('user')}@{session_cfg.get('host')} "
                  f"  {session_cfg.get('contao_root')}")
    else:
        skin.warning("No session. Run: contao-cli-agent connect --host HOST --user USER --root PATH")

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
