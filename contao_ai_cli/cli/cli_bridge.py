"""
bridge group — call the contao-ai-backend-bundle CLI bridge over HTTPS
without going through SSH and the symfony console.

Use cases:
- Bulk-LLM rewrites (translate all news in archive 5 to English) — one
  HTTP call, server-side macro loop, ~10× faster than orchestrating
  N record-update commands from the agent over SSH.
- Recursive operations (clone a page tree with all articles+content) —
  the macro tool walks the tree atomically with the full Phase-9.5
  voter pipeline; doing it through CRUD calls would lose the audit
  trail and per-record refusal handling.

The bridge is OPT-IN: the bundle must be installed on the server, the
target user must have a `tl_user.ai_cli_token` set (see Backend ▸ User ▸
Profile), and the CLI side must be configured via `bridge configure`.
"""
import json
import sys

import click

from contao_ai_cli.core import (
    backend_bridge as bridge_mod,
    session as session_mod,
)
from .helpers import _output


@click.group()
def bridge():
    """Call the backend macro bridge (record_clone, record_rewrite) over HTTPS."""
    pass


@bridge.command("configure")
@click.option("--url", required=True, help="Base URL of the Contao site, e.g. https://c5.example.com")
@click.option("--token", required=True, help="Bridge token in the format <userId>.<random>")
@click.option("--test", is_flag=True, help="After saving, do a sanity-check call (record_clone with invalid args, expects HTTP 422)")
@click.pass_context
def bridge_configure(ctx, url, token, test):
    """Save bridge URL + token to the current session file."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    cfg = session_mod.load_session(session_path)
    if not cfg:
        cfg = {}
    cfg["bridge_url"] = url.rstrip("/")
    cfg["bridge_token"] = token
    session_mod.save_session(cfg, session_path)

    result = {
        "status": "ok",
        "session": session_path,
        "bridge_url": cfg["bridge_url"],
        "bridge_token": bridge_mod.mask_token(token),
    }

    if test:
        client = bridge_mod.BackendBridgeClient(cfg["bridge_url"], token)
        try:
            # Invalid table → controller returns 422 (or tool refuses) — both
            # mean: auth worked, controller routed correctly.
            client.clone(table="__nonexistent__", source_id=1)
            result["test"] = {"status": "unexpected_success", "note": "Expected refusal but call succeeded — token may be wrong scope."}
        except bridge_mod.BridgeError as e:
            if e.status in (403, 422, 500):
                # 403 = voter refusal (tool gated), 422 = invalid args, 500 = tool exec
                # all confirm we reached our controller through valid auth.
                result["test"] = {"status": "ok", "reason": f"Bridge auth OK, server rejected as expected (HTTP {e.status})"}
            elif e.status == 401:
                result["test"] = {"status": "auth_failed", "reason": "401 Unauthorized — token wrong or user disabled"}
                _output(result, ctx.obj.get("as_json"))
                sys.exit(2)
            else:
                result["test"] = {"status": "error", "reason": str(e), "http_status": e.status}
                _output(result, ctx.obj.get("as_json"))
                sys.exit(2)
    _output(result, ctx.obj.get("as_json"))


@bridge.command("status")
@click.pass_context
def bridge_status(ctx):
    """Show current bridge configuration (token masked)."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    cfg = session_mod.load_session(session_path)
    url = cfg.get("bridge_url")
    token = cfg.get("bridge_token")
    if not url or not token:
        _output({"status": "not_configured", "session": session_path}, ctx.obj.get("as_json"))
        return
    _output({
        "status": "configured",
        "session": session_path,
        "bridge_url": url,
        "bridge_token": bridge_mod.mask_token(token),
    }, ctx.obj.get("as_json"))


@bridge.command("clone")
@click.option("--table", required=True, help="Container table to clone (tl_news_archive, tl_calendar, tl_faq_category, tl_page)")
@click.option("--source-id", "source_id", type=int, required=True, help="ID of the source container record")
@click.option("--mod", "modifications", multiple=True, metavar="KEY=VALUE",
              help="Field overrides for the cloned root, e.g. --mod title='New archive'. Repeatable.")
@click.option("--recursive/--no-recursive", default=False,
              help="For container-of-container tables (currently tl_page) clone the entire descendant tree.")
@click.pass_context
def bridge_clone(ctx, table, source_id, modifications, recursive):
    """Clone a record (and cascading children) via record_clone macro."""
    cfg = session_mod.load_session(ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE)
    try:
        client = bridge_mod.from_session_config(cfg)
    except ValueError as e:
        raise click.UsageError(str(e))

    parsed_mods = {}
    for entry in modifications:
        if "=" not in entry:
            raise click.UsageError(f"--mod expects KEY=VALUE, got: {entry}")
        k, v = entry.split("=", 1)
        parsed_mods[k.strip()] = v

    try:
        result = client.clone(table=table, source_id=source_id, modifications=parsed_mods, recursive=recursive)
    except bridge_mod.BridgeError as e:
        _emit_error(e, ctx.obj.get("as_json"))
        sys.exit(1)
    _output(result, ctx.obj.get("as_json"))


@bridge.command("rewrite")
@click.option("--table", required=True, help="Table holding the record to rewrite (tl_news, tl_calendar_events, tl_faq, tl_page, tl_article, tl_content) or a container thereof")
@click.option("--id", "record_id", type=int, required=True, help="ID of the record (or container, with --recursive)")
@click.option("--instructions", required=True, help="Plain-text rewrite instructions, e.g. 'Translate to German, keep technical terms'.")
@click.option("--recursive/--no-recursive", default=False,
              help="Rewrite all child records under the given container.")
@click.pass_context
def bridge_rewrite(ctx, table, record_id, instructions, recursive):
    """Rewrite a record (or all children) via record_rewrite macro (server-side LLM loop)."""
    cfg = session_mod.load_session(ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE)
    try:
        client = bridge_mod.from_session_config(cfg)
    except ValueError as e:
        raise click.UsageError(str(e))

    try:
        result = client.rewrite(table=table, record_id=record_id, instructions=instructions, recursive=recursive)
    except bridge_mod.BridgeError as e:
        _emit_error(e, ctx.obj.get("as_json"))
        sys.exit(1)
    _output(result, ctx.obj.get("as_json"))


def _emit_error(e: bridge_mod.BridgeError, as_json: bool):
    payload = {
        "status": "error",
        "http_status": e.status,
        "message": str(e),
    }
    if e.payload:
        payload["server"] = e.payload
    if as_json:
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        click.echo(click.style(f"[ERROR] HTTP {e.status}: {e}", fg="red"), err=True)
