"""
Output must survive a cp1252 stdout.

Python resolves sys.stdout.encoding to UTF-8 only when a console at code page
65001 is attached. Redirected output, CI, cron and any agent harness capturing
stdout get the locale encoding — cp1252 on a German Windows — and printing a
character outside it raises UnicodeEncodeError mid-line. This has cost four
separate fixes (v0.3.0, v0.3.1, v0.3.2, v0.4.2), each found by spotting one
more symbol, so these tests check the property instead of the symbols.
"""
import ast
import io
import pathlib
from contextlib import redirect_stdout, redirect_stderr

import pytest

from contao_ai_cli.cli import cli_connect
from contao_ai_cli.utils.repl_skin import (
    _ASCII_GLYPHS, _UNICODE_GLYPHS, ReplSkin, _supports_unicode,
)


class _Stream:
    """Minimal stdout stand-in with a fixed encoding."""

    def __init__(self, encoding):
        self.encoding = encoding


def exercise(skin) -> str:
    """Run every output method and return everything it produced."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        skin.print_banner()
        skin.success("saved")
        skin.error("not found")
        skin.warning("unsaved changes")
        skin.info("24 records")
        skin.hint("try help")
        skin.section("Section")
        skin.status("Track 1", "3 clips")
        skin.progress(1, 2, "half")
        skin.table(["id", "title"], [["1", "Foo"]])
        skin.help({"list": "List pages"})
        skin.print_goodbye()
    return buf.getvalue() + skin.prompt("project", modified=True)


class TestSupportsUnicode:
    def test_cp1252_stream_is_rejected(self):
        assert _supports_unicode(_Stream("cp1252")) is False

    def test_utf8_stream_is_accepted(self):
        assert _supports_unicode(_Stream("utf-8")) is True

    def test_stream_without_encoding_is_rejected(self):
        """A stream that cannot say what it accepts is not one to gamble on."""
        assert _supports_unicode(_Stream(None)) is False

    def test_unknown_encoding_is_rejected(self):
        assert _supports_unicode(_Stream("definitely-not-a-codec")) is False

    def test_probe_covers_every_glyph(self):
        """A glyph added to the table must widen the probe automatically."""
        probe = "".join(_UNICODE_GLYPHS.values())
        for name, glyph in _UNICODE_GLYPHS.items():
            assert glyph in probe, name


class TestGlyphSelection:
    def test_ascii_and_unicode_tables_have_the_same_keys(self):
        """A glyph without a fallback is a crash waiting for the next redirect."""
        assert set(_UNICODE_GLYPHS) == set(_ASCII_GLYPHS)

    def test_ascii_table_is_cp1252_safe(self):
        "".join(_ASCII_GLYPHS.values()).encode("cp1252")

    def test_env_var_forces_ascii(self, monkeypatch):
        monkeypatch.setenv("CONTAO_AI_CLI_ASCII", "1")
        assert ReplSkin("contao")._g is _ASCII_GLYPHS

    def test_explicit_argument_wins_over_detection(self):
        assert ReplSkin("contao", ascii_only=False)._g is _UNICODE_GLYPHS
        assert ReplSkin("contao", ascii_only=True)._g is _ASCII_GLYPHS


class TestReplSkinOutput:
    def test_ascii_output_is_cp1252_safe(self):
        """The whole point: on a cp1252 stdout the REPL must still start."""
        exercise(ReplSkin("contao", version="0.0.0", ascii_only=True)).encode("cp1252")

    def test_unicode_output_is_unchanged(self):
        """The fallback must not quietly downgrade a terminal that can render."""
        out = exercise(ReplSkin("contao", version="0.0.0", ascii_only=False))
        assert _UNICODE_GLYPHS["tl"] in out
        assert _UNICODE_GLYPHS["ok"] in out

    def test_prompt_tokens_follow_the_selected_set(self):
        """prompt_toolkit tokens are output too, and were a separate literal."""
        tokens = ReplSkin("contao", ascii_only=True).prompt_tokens("p")
        "".join(text for _, text in tokens).encode("cp1252")


def _unencodable_string_literals(path: pathlib.Path) -> list[tuple[int, str]]:
    """Every cp1252-unencodable string literal in a module, module docstring aside."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = tree.body[0].value if (tree.body and isinstance(tree.body[0], ast.Expr)
                                  and isinstance(tree.body[0].value, ast.Constant)) else None
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if node is skip:  # module docstrings are never printed
            continue
        for ch in node.value:
            try:
                ch.encode("cp1252")
            except UnicodeEncodeError:
                offenders.append((node.lineno, f"U+{ord(ch):04X}"))
    return offenders


# repl_skin.py holds the Unicode glyph table on purpose and never prints from it
# unguarded — TestReplSkinOutput covers it behaviourally instead.
GLYPH_TABLE_MODULE = "repl_skin.py"


@pytest.mark.parametrize("path", sorted(
    p for p in pathlib.Path(__file__).parent.parent.rglob("*.py")
    if "tests" not in p.parts and p.name != GLYPH_TABLE_MODULE
), ids=lambda p: p.name)
def test_module_prints_nothing_a_cp1252_stdout_cannot_take(path):
    offenders = _unencodable_string_literals(path)
    assert not offenders, f"cp1252-unencodable string literals in {path.name}: {offenders}"
