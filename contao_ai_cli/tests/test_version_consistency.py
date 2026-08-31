"""
The version is stated in three places, so a test keeps them equal.

`contao_ai_cli/__init__.py` carried `1.0.0` while the CLI reported `0.8.6` —
stale since some early rename and never noticed, because nothing reads it. That
is exactly why it survived: a constant nobody consumes cannot be caught by
using the program.

It is still a trap. `from contao_ai_cli import __version__` is the obvious
import to reach for, and it would have answered a version that never existed.

The right fix would be one source of truth, but setup.py cannot import the
package it is installing without a bootstrapping dance nobody wants to debug at
install time. So the three stay, and drift between them fails here instead of
being discovered by someone who trusted the wrong one.
"""
import pathlib
import re

import contao_ai_cli
from contao_ai_cli.cli.helpers import __version__ as cli_version

REPO = pathlib.Path(__file__).parent.parent.parent


def setup_py_version() -> str:
    source = (REPO / "setup.py").read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*"([^"]+)"', source)
    assert match, "setup.py no longer states a version in the expected form"
    return match.group(1)


def test_the_package_and_the_cli_agree():
    assert contao_ai_cli.__version__ == cli_version


def test_setup_py_agrees_with_the_cli():
    assert setup_py_version() == cli_version


def test_the_version_looks_like_a_release():
    """A non-numeric segment would make version_tuple() return () and silence
    the update check — the failure mode from v0.5.1."""
    assert re.fullmatch(r"\d+\.\d+\.\d+", cli_version), cli_version
