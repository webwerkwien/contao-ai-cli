"""
Shared helpers for the contao-ai-cli CLI modules.
"""
import json
import pathlib
import shlex
import subprocess
import sys
import urllib.request
import urllib.error
import click

from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.utils.repl_skin import ReplSkin
from contao_ai_cli.core import session as session_mod

__version__ = "0.12.2"

CORE_BUNDLE = "webwerkwien/contao-ai-core-bundle"
BACKEND_BUNDLE = "webwerkwien/contao-ai-backend-bundle"
# The Contao under our three parts. `health` reports it because a site an AI
# agent writes to is the last place an outdated Contao should sit unnoticed —
# and because answering "is this session on a patched version?" otherwise meant
# logging in past the command and reading composer.lock by hand (2026-08-25).
CONTAO_CORE_BUNDLE = "contao/core-bundle"
# The /packages/<name>.json API is cached and lags visibly behind a release —
# it still reported v0.2.7 after v0.2.9 was out. /p2/ is the metadata Composer
# itself resolves against, so it is the one that answers "is an update available".
PACKAGIST_API = f"https://repo.packagist.org/p2/{CORE_BUNDLE}.json"
# Tags, not releases. install_cli_update() installs `git+…@v<x>`, so a tag is
# what "available" actually means here — and asking a different source than the
# one you install from is how the two drift apart. They did: releases stopped
# being created after v0.5.2 while tags carried on to v0.8.0, so
# `releases/latest` answered v0.5.2 for three versions. is_newer_version()
# dutifully said "up to date" — the right words for the wrong reason, and a
# genuine update would have gone unmentioned in exactly the same way.
# per_page=100 because the newest tag has to be on the first page; the list is
# then reduced by version rather than by position, so the API's ordering does
# not matter either.
CLI_TAGS_API = "https://api.github.com/repos/webwerkwien/contao-ai-cli/tags?per_page=100"
CLI_INSTALL_URL = "https://github.com/webwerkwien/contao-ai-cli.git"

# Composer plugins the Contao stack needs. On a Managed Edition these are allowed
# in the Contao Manager's own config.json; only the plain-composer fallback has to
# write them into the project composer.json.
REQUIRED_COMPOSER_PLUGINS = (
    "contao-components/installer",
    "contao/manager-plugin",
)
# Contao 5 uses public/, installations carried over from Contao 4 still use web/.
MANAGER_PHAR_CANDIDATES = (
    "public/contao-manager.phar.php",
    "web/contao-manager.phar.php",
)
COMPOSER_TIMEOUT = 300
CLI_UPDATE_TIMEOUT = 300


def version_tuple(version) -> tuple:
    """
    A release version as a comparable tuple of ints; () for anything else.

    Deliberately narrow: leading `v` is dropped, numeric parts are compared, and
    anything with a non-numeric segment (`dev-main`, `1.2.0-beta`) yields () so
    the caller can treat it as "do not compare". No dependency on `packaging`,
    which is not installed alongside a pipx-installed CLI.
    """
    text = str(version or "").strip().lstrip("v")
    if not text:
        return ()
    parts = text.split(".")
    if not all(p.isdigit() for p in parts):
        return ()
    return tuple(int(p) for p in parts)


def is_newer_version(latest, current) -> bool:
    """
    True only when `latest` is genuinely ahead of `current`.

    A plain `!=` reported "update available: v0.5.0" while v0.5.1 was installed —
    every unreleased working copy looked like it was behind. Anything that cannot
    be compared as a release version (dev builds, pre-releases) returns False:
    silence is better than a wrong arrow.
    """
    a, b = version_tuple(latest), version_tuple(current)
    if not a or not b:
        return False
    # Pad so 0.5 and 0.5.0 compare equal rather than by length.
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def latest_released_tag() -> str | None:
    """The highest release tag in the repository, or None.

    Reduced by version rather than taken from the top of the list: the tags
    endpoint makes no ordering promise, and picking the first entry would make
    the answer depend on something nobody controls. Anything that is not a
    plain release version — `dev-*`, `1.0.0-beta` — yields () from
    version_tuple() and drops out on its own.
    """
    try:
        req = urllib.request.Request(CLI_TAGS_API, headers={"User-Agent": "contao-ai-cli"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            tags = json.loads(resp.read())
    except Exception:
        return None

    if not isinstance(tags, list):
        return None

    best, best_key = None, ()
    for tag in tags:
        name = (tag or {}).get("name", "") if isinstance(tag, dict) else ""
        key = version_tuple(name)
        if key and key > best_key:
            best, best_key = name.lstrip("v"), key

    return best


def check_cli_update() -> dict:
    """Check whether a newer contao-ai-cli has been tagged."""
    latest = latest_released_tag()

    return {
        "current": __version__,
        "latest": latest,
        "update_available": is_newer_version(latest, __version__) if latest else False,
    }


def get_pipx_installed_version() -> str | None:
    """Return the contao-ai-cli version pipx currently reports, or None."""
    try:
        result = subprocess.run(
            ["pipx", "list", "--json"], capture_output=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        data = json.loads(result.stdout)
        return data["venvs"]["contao-ai-cli"]["metadata"]["main_package"]["package_version"]
    except Exception:
        return None


def install_cli_update(latest_version: str) -> dict:
    """
    Reinstall contao-ai-cli at latest_version via pipx.

    'pipx upgrade' cannot move an installation whose spec is pinned to a tag —
    'git+…@v0.4.1' resolves to v0.4.1 forever and pipx reports "already at latest
    version". So the update is a forced reinstall at the requested tag, and the
    result is read back from pipx instead of assumed.

    Returns {"installed": <version or None>, "updated": bool}.
    """
    wanted = latest_version.lstrip("v")
    try:
        subprocess.run(
            ["pipx", "install", "--force", f"git+{CLI_INSTALL_URL}@v{wanted}"],
            check=False, encoding="utf-8", errors="replace", timeout=CLI_UPDATE_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {"installed": get_pipx_installed_version(), "updated": False}
    installed = get_pipx_installed_version()
    return {"installed": installed, "updated": installed == wanted}


def get_installed_package_versions(backend, packages) -> dict:
    """
    Installed versions of several composer packages, in one SSH round-trip.

    Returns {package: version-or-None}. None means "not in installed.json",
    which is also what you get when the file cannot be read at all — the caller
    has no way to tell those apart, so treat None as "assume not installed"
    only where that is the safe reading.
    """
    packages = list(packages)
    result = {p: None for p in packages}
    for package in packages:
        # Interpolated into a PHP string literal inside a single-quoted shell
        # argument. These are module constants, not user input, but a stray
        # quote would break out of both, so refuse rather than guess.
        if "'" in package or '"' in package or "\\" in package:
            raise ValueError(f"Refusing to query a package name with quotes: {package!r}")
    wanted = ",".join(f'"{p}"' for p in packages)
    php_code = (
        f'$w=[{wanted}];'
        'if($d=json_decode(@file_get_contents("vendor/composer/installed.json"),true)){'
        'foreach($d["packages"] as $p)'
        'if(in_array($p["name"],$w,true))echo $p["name"]," ",$p["version"],"\\n";}'
    )
    try:
        out = backend.run_raw(f"{shlex.quote(backend.php_path)} -r '{php_code}'")["stdout"]
    except Exception:
        return result
    for line in out.splitlines():
        name, _, version = line.strip().partition(" ")
        if name in result and version:
            result[name] = version
    return result


def get_core_bundle_installed_version(backend) -> str | None:
    """Return the installed version of contao-ai-core-bundle on the remote server, or None."""
    return get_installed_package_versions(backend, [CORE_BUNDLE])[CORE_BUNDLE]


def get_core_bundle_latest_version() -> str | None:
    """Return the latest stable version of contao-ai-core-bundle from Packagist."""
    try:
        req = urllib.request.Request(PACKAGIST_API, headers={"User-Agent": "contao-ai-cli"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        # /p2/ returns {"packages": {"<name>": [{"version": "v0.2.9", ...}, ...]}},
        # newest first.
        releases = data["packages"][CORE_BUNDLE]
        stable = [
            r["version"] for r in releases
            if "version" in r and not r["version"].startswith("dev-") and "dev" not in r["version"]
        ]
        return stable[0].lstrip("v") if stable else None
    except Exception:
        return None


def detect_contao_manager(backend) -> dict:
    """
    Detect whether the target is a Managed Edition driven by the Contao Manager.

    The phar is what we actually invoke, so its presence plus the manager's own
    config directory decides. 'contao/manager-bundle' in the composer.lock is
    reported alongside as a corroborating signal but is not sufficient on its own —
    without a phar there is nothing to call.

    Returns a dict with keys: phar_path, config_dir, manager_bundle, available.
    """
    # Wrapped in a subshell so a failing 'cd <contao_root>' surfaces as an error
    # instead of probing whatever directory the SSH session happened to land in.
    probe = "( " + "; ".join(
        [f'[ -f {p} ] && echo "phar={p}"' for p in MANAGER_PHAR_CANDIDATES]
        + ['[ -d contao-manager ] && echo "config_dir=1"',
           'grep -q \'"contao/manager-bundle"\' composer.lock 2>/dev/null && echo "manager_bundle=1"',
           "true"]
    ) + " )"
    result = {"phar_path": None, "config_dir": False,
              "manager_bundle": False, "available": False}
    try:
        lines = backend.run_raw(probe)["stdout"].splitlines()
    except ContaoBackendError:
        return result
    for line in lines:
        line = line.strip()
        if line.startswith("phar=") and result["phar_path"] is None:
            result["phar_path"] = line.split("=", 1)[1]
        elif line == "config_dir=1":
            result["config_dir"] = True
        elif line == "manager_bundle=1":
            result["manager_bundle"] = True
    result["available"] = bool(result["phar_path"]) and result["config_dir"]
    return result


def get_missing_allow_plugins(backend) -> list[str]:
    """
    Return the Composer plugins that are NOT yet allowed in the project composer.json.

    An empty list means composer can run without touching the file.
    """
    php_code = (
        'if($j=json_decode(@file_get_contents("composer.json"),true)){'
        '$a=$j["config"]["allow-plugins"]??null;'
        'if($a===true)echo "*";'
        'elseif(is_array($a))foreach($a as $k=>$v){if($v)echo $k,"\\n";}}'
    )
    try:
        out = backend.run_raw(f"{shlex.quote(backend.php_path)} -r '{php_code}'")["stdout"]
    except ContaoBackendError:
        # Unreadable composer.json — assume nothing is allowed and ask.
        return list(REQUIRED_COMPOSER_PLUGINS)
    allowed = {line.strip() for line in out.splitlines() if line.strip()}
    if "*" in allowed:
        return []
    return [p for p in REQUIRED_COMPOSER_PLUGINS if p not in allowed]


def set_allow_plugins(backend, plugins) -> None:
    """Write allow-plugins entries into the project composer.json. Never call unprompted."""
    for plugin in plugins:
        backend.run_raw(f"composer config {shlex.quote('allow-plugins.' + plugin)} true")


def composer_core_bundle(backend, action: str, phar_path: str | None = None,
                         timeout: int = COMPOSER_TIMEOUT) -> dict:
    """
    Run 'composer require|update' for the core bundle on the target server.

    With phar_path set the call goes through the Contao Manager's composer
    passthrough, which uses the manager's own COMPOSER_HOME — the project
    composer.json keeps its own config. Without it, plain composer is used.
    """
    if action not in ("require", "update"):
        raise ValueError(f"Unsupported composer action: {action!r}")
    if phar_path:
        composer = f"{shlex.quote(backend.php_path)} {shlex.quote(phar_path)} composer"
    else:
        composer = "composer"
    return backend.run_raw(
        f"{composer} {action} {CORE_BUNDLE} --no-interaction", timeout=timeout
    )


skin = ReplSkin("contao", version=__version__)


def _get_backend(session_path=None):
    path = session_path or session_mod.DEFAULT_SESSION_FILE
    try:
        return ContaoBackend.from_session(path)
    except ContaoBackendError as e:
        click.echo(click.style(f"[ERROR] {e}", fg="red"), err=True)
        sys.exit(1)


def resolve_bulk_ids(record_id, ids: str | None, ids_from_file: str | None) -> list[int]:
    """Work out which records an update command should touch.

    Exactly one source: the positional ID, ``--ids=39,40,41`` or
    ``--ids-from-file``. A file holds one ID per line; blank lines and anything
    after a ``#`` are ignored, so a list can carry a note about what it is.

    Strict about malformed entries on purpose. The bulk run of 2026-08-29 went
    wrong because a silent skip is indistinguishable from success: 174 IDs went
    in, one record came out changed, and the summary read "1 succeeded, 0
    failed". Anything unparseable is named and refused instead.

    :raises ValueError: on no source, more than one source, or a bad entry
    """
    given = [s for s in (record_id, ids, ids_from_file) if s is not None]
    if not given:
        raise ValueError("No record given. Pass an ID, --ids=1,2,3 or --ids-from-file FILE.")
    if len(given) > 1:
        raise ValueError("Pass exactly one of: an ID, --ids or --ids-from-file.")

    if record_id is not None:
        return [int(record_id)]

    if ids_from_file is not None:
        try:
            raw = pathlib.Path(ids_from_file).read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"Cannot read {ids_from_file}: {e}") from e
        tokens = []
        for line in raw.splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                tokens.extend(line.replace(",", " ").split())
        source = ids_from_file
    else:
        tokens = [t for t in ids.replace(",", " ").split() if t]
        source = "--ids"

    resolved: list[int] = []
    for token in tokens:
        if not token.isdigit() or int(token) < 1:
            raise ValueError(f'"{token}" in {source} is not a valid record ID.')
        value = int(token)
        if value not in resolved:
            resolved.append(value)

    if not resolved:
        raise ValueError(f"{source} did not contain a single record ID.")

    return resolved


def bulk_id_options(f):
    """The `--ids` / `--ids-from-file` pair shared by every entity update command."""
    f = click.option(
        "--ids-from-file", "ids_from_file", default=None, metavar="FILE",
        help="Read record IDs from a file, one per line (# starts a comment)",
    )(f)
    f = click.option(
        "--ids", default=None, metavar="1,2,3",
        help="Apply the same --set values to several records in one connection",
    )(f)
    return f


def dispatch_update(backend, command: str, record_id, ids, ids_from_file, fields: dict) -> dict:
    """Route an update to the single-record or the bulk path.

    The *source* decides, not the count: a positional ID keeps the exact response
    shape every existing caller already parses, while `--ids`/`--ids-from-file`
    always returns the bulk summary — even for one record, so a script does not
    have to branch on how many IDs it happened to pass.

    :raises click.UsageError: when the ID sources are missing, mixed or malformed
    """
    from contao_ai_cli.core.contao_ops import run_bulk_update, run_update

    try:
        targets = resolve_bulk_ids(record_id, ids, ids_from_file)
    except ValueError as e:
        raise click.UsageError(str(e)) from e

    if record_id is not None:
        return run_update(backend, command, targets[0], fields)

    return run_bulk_update(backend, command, targets, fields)


def configure_output_encoding(*streams) -> None:
    """Put stdout and stderr on UTF-8 so record data cannot kill a command.

    Python resolves ``sys.stdout.encoding`` to UTF-8 only when a console at code
    page 65001 is attached. Redirected output, CI, cron and any agent harness
    capturing stdout get the locale encoding instead — cp1252 on a German
    Windows — and a single character outside it raises UnicodeEncodeError
    halfway through a line.

    Four earlier rounds (v0.3.0, v0.3.1, v0.3.2, v0.4.2) each fixed this by
    removing a character from our own source, and test_output_encoding.py keeps
    that clean. It cannot help here: on 2026-08-29 ``page read 98`` crashed on a
    U+FFFD that came out of the *record*. `_output()` serialises with
    ``ensure_ascii=False``, so anything a customer types is one umlaut away from
    the same crash. Fixing the stream covers the whole class at once.

    Silent on a stream that cannot be reconfigured — the ASCII fallback in
    repl_skin.py still stands behind it.
    """
    for stream in streams or (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # StringIO, an already-detached stream, a test double — all fine.
            pass


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


def _detect_core_bundle(backend) -> bool:
    """Check if contao-ai-core-bundle commands are available on the server."""
    try:
        result = backend.run("list")
        return "contao:user:update" in result["stdout"]
    except Exception:
        return False


def parse_set_fields(fields) -> dict:
    """
    Turn repeated `--set FIELD=VALUE` into a dict.

    A malformed entry is an error rather than something to drop: silently
    ignoring `--set titel Neu` would report a successful update that changed
    nothing.
    """
    parsed = {}
    for raw in fields:
        key, sep, value = raw.partition("=")
        if not sep or not key:
            raise click.UsageError(f"--set expects FIELD=VALUE, got: {raw!r}")
        parsed[key] = value
    return parsed


def ask_yes_no(question: str, default: bool = False) -> bool | None:
    """
    Ask a yes/no question and tell "no answer" apart from "no".

    Written by hand rather than via `click.confirm`, and the reason is a safety
    one. `click.confirm` catches KeyboardInterrupt and EOFError together and
    re-raises both as `Abort` with `from None`, so the cause is gone and the two
    cannot be told apart afterwards:

        except (KeyboardInterrupt, EOFError):
            raise Abort() from None          # click/termui.py

    That collapse is fine for click and fatal for us. `confirm_action` treats
    "nobody answered" as *proceed* — so catching `Abort` there and returning
    True would turn a deliberate Ctrl-C into "yes, delete it". The distinction
    has to survive, so the read happens here.

    Returns True or False for an actual answer, and **None when nobody was
    there to give one** (EOF). Ctrl-C is not an answer and not a silence — it is
    a deliberate cancel, and it propagates as `click.Abort`.
    """
    suffix = " [Y/n]: " if default else " [y/N]: "

    while True:
        try:
            click.echo(question + suffix, nl=False)
            value = input().strip().lower()
        except EOFError:
            click.echo("")
            return None
        except KeyboardInterrupt:
            raise click.Abort() from None

        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        if value == "":
            return default
        click.echo("Error: invalid input")


def confirm_delete(what: str, assume_yes: bool = False) -> bool:
    """
    Ask before deleting, unless told not to or nobody is there to answer.

    The Contao back end asks: DefaultOperationsListener puts
    `onclick="if(!confirm(...))return false"` on the generic delete operation of
    every DCA. A prompt here is therefore consistent with Contao rather than
    stricter than it. But this CLI is driven by agents and scripts as much as by
    people, and a prompt that nothing can answer is worse than no prompt — so it
    only appears on a terminal, and --yes skips it.
    """
    return confirm_action(f"Delete {what}?", assume_yes)


def confirm_action(question: str, assume_yes: bool = False) -> bool:
    """
    The prompt behind confirm_delete, for operations that are not deletions.

    `undo restore` writes rows back into live tables and can collide with a
    record that has taken the ID since — worth asking about, but "Delete …?"
    would be the wrong question. Same rules either way: only on a terminal,
    because a prompt nothing can answer is worse than no prompt, and --yes
    skips it.

    Careful: `isatty()` is not proof that anyone is there. Under Git Bash it
    reported True for `< /dev/null`, and two calls in one session disagreed
    (found 2026-08-31). Where it wrongly says True, the prompt used to raise
    `Abort` and kill the command — safe, since nothing was deleted, but every
    `delete` without --yes died in an agent harness. So "nobody answered" is
    now decided by the read itself, and it lands on the same outcome as having
    no terminal at all. A Ctrl-C still cancels: it is an answer, not a silence.
    """
    if assume_yes:
        return True
    try:
        interactive = sys.stdin.isatty()
    except Exception:
        interactive = False
    if not interactive:
        return True
    answered = ask_yes_no(question, default=False)
    return True if answered is None else answered


def confirm_escalation(question: str) -> bool:
    """
    Ask whether to do the *more* consequential of two things — and say no when
    nobody is there to answer.

    The mirror image of confirm_action, and the difference is the headless
    default, not the wording. There, the caller already typed `delete`: the
    prompt is a net for a human, so with no terminal the command proceeds.
    Here the question decides between two outcomes the caller did not choose
    between — `newsletter subscriber-create` without --active or --inactive —
    and the consequential one must not be what silence selects.

    Getting that backwards would be worse than having no prompt at all: it
    would look like a safeguard in the source and wave everything through in
    exactly the setting this CLI usually runs in. Per the note on
    confirm_action, agent harnesses, CI and cron are the normal case here, not
    the exception — so `return True` on a missing tty would mean the guard
    never once fires where it matters.

    Callers that want the escalation without a terminal pass the explicit flag;
    that is the point of the flag.

    Careful: `isatty()` is not trustworthy on its own, and the live run of 2026-08-31
    is why this catches as well as asks. Two invocations in the same Git Bash
    session reported different answers, and `python -c … < /dev/null` reported
    **True** — the emulated device passes for a terminal. Where it wrongly says
    True, `click.confirm` finds nothing to read and raises `Abort`, killing the
    command outright.

    So the guarantee is not "isatty said there is a terminal" but the stronger
    one: **the escalation happens only when a human actively answers yes.**
    Anything else — no terminal, a terminal nobody is at, EOF — is a no, and the
    caller carries on with the harmless outcome instead of dying.
    """
    try:
        interactive = sys.stdin.isatty()
    except Exception:
        interactive = False
    if not interactive:
        return False
    # None means nobody answered — a no here, where confirm_action reads the
    # same silence as a yes. That is the whole difference between the two.
    return ask_yes_no(question, default=False) is True


def _require_core_bundle(ctx, command_name: str):
    """
    Raise UsageError with an install hint if the core bundle is missing.

    Named `_require_core_bundle` until v0.5.0, after the core bundle's original name
    `contao-cli-bridge`. That collided with the unrelated `bridge` command group,
    which talks to contao-ai-backend-bundle over HTTP — and the collision was read
    as evidence that editing was meant to go through the backend, which it was not.
    """
    session_path = pathlib.Path(ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE)

    # Three different failures used to arrive as one sentence, because a bare
    # `except Exception: available = False` cannot tell them apart. On
    # 2026-09-01 a mistyped session name (`c5` for `c5-axeltest`) answered
    # "contao-ai-core-bundle is not installed on this server" — for a server
    # that had never been contacted and does have the bundle. The advice sent
    # the reader to `composer require` on an installation that does not exist.
    #
    # Only the third branch below is a statement about the server. The first
    # two are statements about this machine, and saying so is the whole fix.
    if not session_path.exists():
        raise click.UsageError(_no_such_session(session_path))

    try:
        cfg = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise click.UsageError(
            f"Session file {session_path} cannot be read: {e}\n"
            f"Recreate it with: contao-ai-cli connect --host HOST --user USER --root /path/to/contao"
        ) from e

    # Sessions written before v0.5.0 carry the old key.
    if not cfg.get("core_bundle_available", cfg.get("bridge_available", False)):
        raise click.UsageError(
            f"'{command_name}' requires contao-ai-core-bundle which is not installed on this server.\n"
            f"Install with: composer require webwerkwien/contao-ai-core-bundle"
        )


def _no_such_session(session_path: pathlib.Path) -> str:
    """
    Name the session that was asked for, and the ones that exist.

    The names are already on disk and `session-list` already reads them, so
    withholding them here would be a dead end that knows the answer — the same
    failure this message is being fixed for, one size smaller.
    """
    known = [s["name"] for s in session_mod.list_sessions()]
    wanted = session_path.stem

    if not known:
        return (
            f"No session named '{wanted}' — no sessions are configured at all.\n"
            f"Create one with: contao-ai-cli connect --host HOST --user USER --root /path/to/contao"
        )

    return (
        f"No session named '{wanted}' (looked for {session_path}).\n"
        f"Known sessions: {', '.join(sorted(known))}\n"
        f"This says nothing about the server — nothing was asked of one."
    )
