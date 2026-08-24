"""
connect, session-list, session-delete commands.
"""
import json
import sys
import click

from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.core import session as session_mod, backup as backup_mod
from .helpers import (
    _output, _detect_core_bundle, CLI_INSTALL_URL,
    check_cli_update, install_cli_update,
    get_core_bundle_installed_version, get_core_bundle_latest_version,
    detect_contao_manager, get_missing_allow_plugins, set_allow_plugins,
    composer_core_bundle,
)


def _install_core_bundle(b, manager, action: str) -> bool:
    """
    Install ('require') or update the core bundle on the target server.

    On a Managed Edition this goes through the Contao Manager's composer
    passthrough: the manager supplies its own allow-plugins config, so the
    project composer.json is left alone. Every other installation falls back to
    plain composer — and that path has to ask first, because it can only run
    after allow-plugins has been written into the project composer.json.

    Returns True if the bundle was installed/updated.
    """
    verb, done, noun = (
        ("Installing", "installed", "Installation") if action == "require"
        else ("Updating", "updated", "Update")
    )

    if manager["available"]:
        click.echo(f"Contao Manager detected ({manager['phar_path']}) — "
                   f"using its Composer passthrough, composer.json config stays untouched.")
    else:
        missing = get_missing_allow_plugins(b)
        if missing:
            click.echo(click.style(
                "\n[!] No Contao Manager found — falling back to plain composer.\n"
                "    Composer will refuse to run the Contao plugins unless they are\n"
                "    allowed in the project composer.json. Proceeding writes:\n"
                + "".join(f"      config.allow-plugins.{p} = true\n" for p in missing),
                fg="yellow",
            ))
            if not click.confirm("Modify composer.json on the server to allow these plugins?",
                                 default=False):
                click.echo(f"Skipped — contao-ai-core-bundle was not {done}.")
                return False
            try:
                set_allow_plugins(b, missing)
            except ContaoBackendError as e:
                click.echo(click.style(f"[ERROR] Could not set allow-plugins: {e}", fg="red"))
                return False
            click.echo(click.style(
                f"[i] composer.json modified: allow-plugins set for {', '.join(missing)}.",
                fg="yellow"
            ))

    click.echo(f"{verb} via composer (this may take a moment)...")
    try:
        composer_core_bundle(b, action, manager["phar_path"] if manager["available"] else None)
        b.run("cache:warmup --env=prod")
    except ContaoBackendError as e:
        click.echo(click.style(f"[ERROR] {noun} failed: {e}", fg="red"))
        return False
    click.echo(click.style(f"[OK] contao-ai-core-bundle {done}.", fg="green"))
    return True


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
            f"[!] contao-ai-cli update available: v{cli_update['current']} -> v{cli_update['latest']}",
            fg="yellow"
        ))
        if click.confirm("Install CLI update now?", default=True):
            click.echo("Updating contao-ai-cli...")
            outcome = install_cli_update(cli_update["latest"])
            if outcome["updated"]:
                click.echo(click.style(
                    f"[OK] contao-ai-cli v{outcome['installed']} installed. "
                    "Please restart contao-ai-cli.", fg="green"
                ))
            else:
                # Never report success we have not seen: an older release claimed
                # the update had landed while pipx had in fact changed nothing.
                click.echo(click.style(
                    f"[ERROR] Update did not take effect — still on "
                    f"v{outcome['installed'] or 'unknown'}. Install it manually:\n"
                    f"    pipx install --force git+{CLI_INSTALL_URL}@v{cli_update['latest']}",
                    fg="red"
                ))
    else:
        click.echo(f"contao-ai-cli v{cli_update['current']}: up to date.")

    # ── 2. core-bundle check ──────────────────────────────────────────────────
    installed_version = get_core_bundle_installed_version(b)
    manager = detect_contao_manager(b)
    core_bundle = False

    if installed_version is None:
        click.echo("\ncontao-ai-core-bundle: not installed — enables full CRUD support.")
        # default=False: this writes to the project's composer.json.
        if click.confirm("Install contao-ai-core-bundle now?", default=False):
            core_bundle = _install_core_bundle(b, manager, "require")
    else:
        if installed_version.startswith("dev-"):
            click.echo(f"contao-ai-core-bundle {installed_version}: development version, skipping update check.")
        else:
            latest_version = get_core_bundle_latest_version()
            if latest_version and installed_version.lstrip("v") != latest_version.lstrip("v"):
                click.echo(click.style(
                    f"\n[!] contao-ai-core-bundle update available: "
                    f"{installed_version} -> v{latest_version}",
                    fg="yellow"
                ))
                # default=False: this writes to the project's composer.json.
                if click.confirm("Update contao-ai-core-bundle now?", default=False):
                    _install_core_bundle(b, manager, "update")
            else:
                click.echo(f"contao-ai-core-bundle {installed_version}: up to date.")
        core_bundle = True

    # ── Save the core-bundle flag to the session ──────────────────────────────
    with open(session_path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["core_bundle_available"] = core_bundle
    cfg.pop("bridge_available", None)  # pre-0.5.0 name
    with open(session_path, "w", encoding="utf-8") as f:
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
