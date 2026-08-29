"""
The fifth round of the cp1252 problem — and the first one not about literals.

Rounds one to four (v0.3.0, v0.3.1, v0.3.2, v0.4.2) each removed a character
from our own source, and test_output_encoding.py guards that: no module may
hold a string literal a cp1252 stdout cannot take.

On 2026-08-29 `page read 98` crashed anyway:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\ufffd'
      … click/utils.py line 321 in echo → cp1252.py line 19

The character came from the *record*, not from us — no literal test can reach
it, and the next one will arrive with the next umlaut a customer types. So the
stream is fixed instead of the payload: `_output()` serialises with
`ensure_ascii=False`, which only holds together on a stdout that can carry it.
"""
import io
import json
import sys

import pytest

from contao_ai_cli.cli.helpers import _output, configure_output_encoding


def cp1252_stream() -> io.TextIOWrapper:
    """A stdout stand-in like the one an agent harness hands us on Windows."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")


class TestConfigureOutputEncoding:
    def test_switches_a_cp1252_stream_to_utf8(self):
        stream = cp1252_stream()
        assert stream.encoding == "cp1252"

        configure_output_encoding(stream)

        assert stream.encoding.lower().replace("-", "") == "utf8"

    def test_the_character_that_crashed_page_read_now_writes(self):
        stream = cp1252_stream()
        configure_output_encoding(stream)

        stream.write("�")  # U+FFFD, straight out of the Balbersteine record
        stream.flush()

        assert stream.buffer.getvalue() == "�".encode("utf-8")

    def test_umlauts_survive_as_utf8_not_as_escapes(self):
        stream = cp1252_stream()
        configure_output_encoding(stream)

        stream.write("Höhenmeter")
        stream.flush()

        assert stream.buffer.getvalue().decode("utf-8") == "Höhenmeter"

    def test_leaves_a_utf8_stream_alone(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="")

        configure_output_encoding(stream)

        assert stream.encoding.lower().replace("-", "") == "utf8"

    def test_survives_a_stream_that_cannot_be_reconfigured(self):
        """StringIO and the doubles used across the suite have no reconfigure()."""
        configure_output_encoding(io.StringIO())  # must not raise

    def test_survives_a_stream_that_refuses(self):
        class Stubborn:
            encoding = "cp1252"

            def reconfigure(self, **kwargs):
                raise ValueError("detached")

        configure_output_encoding(Stubborn())  # must not raise

    def test_defaults_to_stdout_and_stderr(self, monkeypatch):
        out, err = cp1252_stream(), cp1252_stream()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)

        configure_output_encoding()

        assert out.encoding.lower().replace("-", "") == "utf8"
        assert err.encoding.lower().replace("-", "") == "utf8", "Errors carry record data too."


class TestOutputHelper:
    """The helper at the actual crash site, exercised end to end."""

    @pytest.mark.parametrize("payload", [
        {"title": "Balbersteine �"},
        {"title": "Über den Höhenweg"},
        {"nested": [{"description": "Gehzeit – 2 h"}]},
    ])
    def test_json_output_reaches_a_cp1252_stdout_intact(self, monkeypatch, payload):
        stream = cp1252_stream()
        monkeypatch.setattr(sys, "stdout", stream)
        configure_output_encoding()

        _output(payload, as_json=True)
        stream.flush()

        assert json.loads(stream.buffer.getvalue().decode("utf-8")) == payload
