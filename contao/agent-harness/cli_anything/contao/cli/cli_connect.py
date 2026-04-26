"""
connect, session-list, session-delete commands.
"""
import json
import sys
import click

from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.core import session as session_mod, backup as backup_mod
from .helpers import (
    _output, _detect_bridge,
    check_cli_update, get_core_bundle_installed_version, get_core_bundle_latest_version,
)


@click.command()
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
        "\n[!] Warning: contao-ai-cli can irreversibly modify or delete data on the target server.\n"
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
            click.echo(click.style("[OK] Backup created.", fg="green"))
            if backup_result.get("output"):
                click.echo(backup_result["output"].strip())

    except ContaoBackendError as e:
        click.echo(click.style(f"[ERROR] Connection failed: {e}", fg="red"), err=True)
        sys.exit(1)

    b = ContaoBackend.from_session(session_path)

    # ── 1. CLI self-update check ──────────────────────────────────────────────
    click.echo("\nChecking for updates...")
    cli_update = check_cli_update()
    if cli_update["update_available"]:
        click.echo(click.style(
            f"[!] contao-ai-cli update available: v{cli_update['current']} → v{cli_update['latest']}",
            fg="yellow"
        ))
        if click.confirm("Install CLI update now?", default=True):
            import subprocess as _sp
            click.echo("Updating contao-ai-cli...")
            _sp.run(
                ["pipx", "upgrade", "contao-ai-cli"],
                check=False,
            )
            click.echo(click.style(
                "[OK] Update installed. Please restart contao-ai-cli.", fg="green"
            ))
    else:
        click.echo(f"contao-ai-cli v{cli_update['current']}: up to date.")

    # ── 2. core-bundle check ──────────────────────────────────────────────────
    installed_version = get_core_bundle_installed_version(b)
    bridge = False

    if installed_version is None:
        click.echo("\ncontao-ai-core-bundle: not installed — enables full CRUD support.")
        if click.confirm("Install contao-ai-core-bundle now?", default=True):
            click.echo("Installing via composer (this may take a moment)...")
            try:
                b.run_raw("composer config allow-plugins.contao-components/installer true")
                b.run_raw("composer config allow-plugins.contao/manager-plugin true")
                b.run_raw(
                    "composer require webwerkwien/contao-ai-core-bundle --no-interaction",
                    timeout=180,
                )
                b.run("cache:warmup --env=prod")
                click.echo(click.style("[OK] contao-ai-core-bundle installed.", fg="green"))
                bridge = True
            except ContaoBackendError as e:
                click.echo(click.style(f"[ERROR] Installation failed: {e}", fg="red"))
    else:
        if installed_version.startswith("dev-"):
            click.echo(f"contao-ai-core-bundle {installed_version}: development version, skipping update check.")
        else:
            latest_version = get_core_bundle_latest_version()
            if latest_version and installed_version.lstrip("v") != latest_version.lstrip("v"):
                click.echo(click.style(
                    f"\n[!] contao-ai-core-bundle update available: "
                    f"{installed_version} → v{latest_version}",
                    fg="yellow"
                ))
                if click.confirm("Update contao-ai-core-bundle now?", default=True):
                    click.echo("Updating via composer...")
                    try:
                        b.run_raw("composer config allow-plugins.contao-components/installer true")
                        b.run_raw("composer config allow-plugins.contao/manager-plugin true")
                        b.run_raw(
                            "composer update webwerkwien/contao-ai-core-bundle --no-interaction",
                            timeout=180,
                        )
                        b.run("cache:warmup --env=prod")
                        click.echo(click.style("[OK] contao-ai-core-bundle updated.", fg="green"))
                    except ContaoBackendError as e:
                        click.echo(click.style(f"[ERROR] Update failed: {e}", fg="red"))
            else:
                click.echo(f"contao-ai-core-bundle {installed_version}: up to date.")
        bridge = True

    # ── Save bridge flag to session ───────────────────────────────────────────
    with open(session_path) as f:
        cfg = json.load(f)
    cfg["bridge_available"] = bridge
    with open(session_path, "w") as f:
        json.dump(cfg, f, indent=2)


@click.command("session-list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def session_list(ctx, as_json):
    """List saved sessions."""
    sessions = session_mod.list_sessions()
    _output(sessions, as_json or ctx.obj.get("as_json"))


@click.command("session-delete")
@click.option("--name", default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def session_delete(ctx, name, as_json):
    """Delete a session."""
    path = session_mod.get_session_path(name)
    session_mod.delete_session(path)
    _output({"status": "deleted", "path": path}, as_json or ctx.obj.get("as_json"))
