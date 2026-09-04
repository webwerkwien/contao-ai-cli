"""Turns an unexpected failure into a report the user can hand to the maintainer.

Why the CLI needs its own
-------------------------
The bundles carry `ErrorReportBuilder` in PHP, but it runs on the server. Most
CLI failures never get that far: no SSH key, host unreachable, a bridge that
answers 500, a bug in this code. Those have to be described where they happen.

This is the one place where the same idea legitimately exists twice, because it
exists in two runtimes. To keep that from drifting into two different reports,
the field names here are the same as in the PHP builder -- `zeitpunkt`,
`komponente`, `versionen`, `umgebung`, `ausnahme` -- so a report reads the same
whichever end produced it.

What never reaches a report
---------------------------
Argument values, session passwords, tokens, the contents of anything read or
written. Absolute paths are shortened: a home directory names the user, and that
is not diagnostic information.

The consent question
--------------------
This module builds text and returns it. It does not send anything, and it does
not decide what happens next -- the calling agent does, and CLAUDE.md tells it
that a report is not passed on without the user's agreement. That is a weaker
assurance than a technical one, which is exactly why the allow-list above it
matters more: a report that carries nothing harmful does not depend on anyone
behaving well.
"""
import os
import platform
import re
import sys
import traceback
from datetime import datetime, timezone

from contao_ai_cli import __version__

NOTICE = (
    "Dieser Bericht stammt aus einer Contao-Installation. "
    "Vor der Weitergabe an Dritte ist die ausdrueckliche Zustimmung des Anwenders einzuholen."
)

# Same three shapes as CredentialMasker in the core bundle. Deliberately loose
# on the tail so a hyphenated prefix (sk-proj-, sk-or-v1-) cannot end the match.
_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "sk-***"),
    (re.compile(r"AIza[A-Za-z0-9_-]{20,}"), "AIza***"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"), "Bearer ***"),
]

_MIN_LITERAL_LENGTH = 8
_MAX_FRAMES = 25


def mask(text: str, *known_secrets: str) -> str:
    """Strike literal secrets first, then the pattern net.

    The literal pass is the one that works: we hold the token, so we do not have
    to guess its shape. The patterns only cover secrets we do not hold -- one
    pasted into a prompt, a bearer token from somewhere else.
    """
    for secret in known_secrets:
        if secret and len(secret) >= _MIN_LITERAL_LENGTH:
            text = text.replace(secret, "***")

    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)

    return text


def shorten_path(path: str) -> str:
    """Locate the code without describing the machine.

    An absolute path names the user (`C:\\Users\\booki\\...`, `/home/michael/...`)
    and says nothing a maintainer needs. Everything from `contao_ai_cli/` on is
    kept because that is the part that identifies our code; anything else is
    reduced to its file name.
    """
    normalised = path.replace("\\", "/")
    marker = "/contao_ai_cli/"

    position = normalised.rfind(marker)
    if position != -1:
        return normalised[position + 1:]

    return os.path.basename(normalised)


def _frames(exc: BaseException, known_secrets) -> list:
    """Our frames in full, foreign runs collapsed to one line.

    Same treatment as the PHP side, and for the same reason: a traceback is
    mostly interpreter and library plumbing, and collapsing it also drops the
    surrounding lines of source that `traceback` would otherwise render.
    """
    lines = []
    skipped = 0

    for frame in traceback.extract_tb(exc.__traceback__)[:_MAX_FRAMES]:
        own = "contao_ai_cli" in frame.filename.replace("\\", "/")

        if not own:
            skipped += 1
            continue

        if skipped:
            lines.append("... %d Aufruf(e) ausserhalb von contao-ai" % skipped)
            skipped = 0

        lines.append(mask(
            "%s() in %s:%s" % (frame.name, shorten_path(frame.filename), frame.lineno),
            *known_secrets,
        ))

    if skipped:
        lines.append("... %d Aufruf(e) ausserhalb von contao-ai" % skipped)

    return lines


def build(exc: BaseException, context: dict | None = None, known_secrets=()) -> str:
    """Render a report for one failure.

    `context` may carry `befehl` (the invoked command name) and `status` (an HTTP
    status from the bridge). Values from the user's arguments do not belong in
    it -- pass the command name, never what was passed to it.
    """
    context = context or {}

    summary = [
        ("zeitpunkt", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC"),
        ("komponente", "cli"),
        ("versionen.cli", __version__),
        ("umgebung.python", platform.python_version()),
        ("umgebung.os", platform.system()),
        ("ausnahme.klasse", type(exc).__name__),
    ]

    tb = traceback.extract_tb(exc.__traceback__)
    if tb:
        summary.append(("ausnahme.datei", shorten_path(tb[-1].filename)))
        summary.append(("ausnahme.zeile", str(tb[-1].lineno)))

    for key in ("befehl", "status"):
        if context.get(key) is not None:
            summary.append((key, str(context[key])))

    lines = [
        "> WARNUNG: " + NOTICE,
        "",
        "## Fehlerbericht contao-ai",
        "",
        "| Feld | Wert |",
        "|---|---|",
    ]
    lines += ["| %s | `%s` |" % (label, value) for label, value in summary]

    message = mask(str(exc), *known_secrets)
    if message:
        lines += ["", "### Meldung", "", "```", message, "```"]

    frames = _frames(exc, known_secrets)
    if frames:
        lines += ["", "### Aufrufkette", "", "```"] + frames + ["```"]

    return "\n".join(lines) + "\n"


def is_reportable(exc: BaseException) -> bool:
    """Is this a defect, or a message?

    The same line the bundles draw between 500 and 422: a bridge answering 5xx
    broke, a bridge answering 4xx is telling us something about the request --
    wrong token, missing route, malformed body. The second is not worth a report
    and would train users to send noise.

    Anything that is not a `BridgeError` and got here at all is unexpected by
    definition: Click handles its own exceptions and `ContaoBackendError` is a
    `ClickException`, so a plain exception reaching the top means nobody planned
    for it.
    """
    status = getattr(exc, "status", None)

    if status is not None:
        try:
            return int(status) >= 500
        except (TypeError, ValueError):
            return True

    return True


def emit(exc: BaseException, context: dict | None = None, known_secrets=()) -> None:
    """Write the report to stderr, below the error itself.

    stderr on purpose: stdout carries data a caller may be parsing, and a report
    appended there would corrupt it. The exit code is left to the caller.
    """
    sys.stderr.write("\n" + build(exc, context, known_secrets))
