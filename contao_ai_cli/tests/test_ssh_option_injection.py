"""
A connection value must never be read by ssh as an option of its own.

Audit 2026-09-02, finding C-10, confirmed with a working proof of concept before
it was fixed. `_ssh_args()` appended `user@host` with nothing marking the end of
the options, so a session whose user began with `-o` made ssh execute an
arbitrary command on the LOCAL machine:

    contao-ai-cli connect --user '-oProxyCommand=cmd.exe /c … & rem ' --host …

ssh parsed the argument as `-o ProxyCommand=…` and spawned it. The trailing
`& rem ` swallows the `@host` that gets appended, which is the only part that
took a second attempt.

The user is the reachable end of this: it is a `connect` option, it lands in the
session file, and an agent handed this CLI can set it from something it read.

## Two defences, on purpose

`--` before the destination is what actually stops ssh, and it would be enough.
`_reject_option_lookalike()` exists anyway, because the same values also reach
scp, the session file and error messages — and because a check at the door can
say what is wrong while someone can still fix it.

## The measurement that nearly went the other way

A first run through Git Bash's `ssh` showed nothing executing, and the finding
was almost dismissed as a false positive. `_find_ssh()` selects
`C:\\Windows\\System32\\OpenSSH\\ssh.exe` on Windows, and only there does it
fire. A result belongs to the binary it was taken from.
"""
import subprocess
from unittest.mock import patch

import pytest

from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError


def make_backend(**overrides) -> ContaoBackend:
    kwargs = dict(
        host="example.com", user="deploy", contao_root="/var/www/contao",
        key_path="/home/user/.ssh/id_ed25519", port=22,
    )
    kwargs.update(overrides)
    with patch.object(ContaoBackend, "_find_ssh", return_value="/usr/bin/ssh"), \
         patch.object(ContaoBackend, "_default_key", return_value="/home/user/.ssh/id_ed25519"):
        return ContaoBackend(**kwargs)


PAYLOADS = [
    "-oProxyCommand=cmd.exe /c calc",
    "-oPermitLocalCommand=yes",
    "-F/tmp/evil_ssh_config",
    "-",
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_a_user_that_looks_like_an_option_is_refused(payload):
    with pytest.raises(ContaoBackendError) as excinfo:
        make_backend(user=payload)

    assert "begins with '-'" in str(excinfo.value)


@pytest.mark.parametrize("payload", PAYLOADS)
def test_a_host_that_looks_like_an_option_is_refused(payload):
    with pytest.raises(ContaoBackendError):
        make_backend(host=payload)


def test_a_key_path_that_looks_like_an_option_is_refused():
    with pytest.raises(ContaoBackendError) as excinfo:
        make_backend(key_path="-oProxyCommand=cmd.exe /c calc")

    assert "key path" in str(excinfo.value)


def test_a_key_path_may_contain_spaces():
    # `C:\Program Files\…` is an ordinary key location, and the path travels as
    # its own argv element after `-i`, where a space cannot split it. Rejecting
    # whitespace here would have broken real installations for no gain.
    backend = make_backend(key_path=r"C:\Program Files\keys\id_ed25519")

    assert r"C:\Program Files\keys\id_ed25519" in backend._ssh_args()


@pytest.mark.parametrize("bad", ["exa mple.com", "example.com\nHost evil", "ex\tample"])
def test_whitespace_and_control_characters_are_refused(bad):
    with pytest.raises(ContaoBackendError):
        make_backend(host=bad)


def test_the_destination_is_separated_by_a_double_dash():
    args = make_backend()._ssh_args()

    assert "--" in args, "nothing marks the end of ssh's options"
    assert args[args.index("--") + 1] == "deploy@example.com", \
        "the destination must be the first thing after --"
    assert args.index("--") == len(args) - 2, "-- must come last, before the destination only"


def test_scp_separates_its_operands_too():
    backend = make_backend()
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    with patch("subprocess.run", return_value=completed) as run:
        backend.scp_upload("local.txt", "/remote/local.txt")

    args = run.call_args[0][0]
    assert "--" in args
    assert args[args.index("--") + 1:] == ["local.txt", "deploy@example.com:/remote/local.txt"]


def test_an_ordinary_session_still_works():
    # The guard has to let normal values through, or it is just an outage.
    args = make_backend(user="web_werk_wien_SSH", host="5.9.34.63", port=2222)._ssh_args()

    assert "web_werk_wien_SSH@5.9.34.63" in args
    assert "2222" in args
