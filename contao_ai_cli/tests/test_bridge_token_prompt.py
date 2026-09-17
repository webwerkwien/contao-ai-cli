from unittest.mock import patch

import click
import pytest

from contao_ai_cli.cli.helpers import resolve_password, resolve_token


def test_errors_name_the_stdin_flag_of_the_option():
    with pytest.raises(click.UsageError) as e:
        resolve_token("x", True)
    assert "--token-stdin" in str(e.value) and "--password-stdin" not in str(e.value)


def test_a_described_value_keeps_its_real_stdin_flag():
    """Review 2026-09-17: `hash-password` passes what="the PASSWORD argument"."""
    with pytest.raises(click.UsageError) as e:
        resolve_password(None, False, what="the PASSWORD argument")
    assert "--password-stdin" in str(e.value) and "argument-stdin" not in str(e.value)


def test_a_terminal_without_token_gets_a_hidden_prompt():
    with patch("contao_ai_cli.cli.helpers.stdin_is_console", return_value=True), \
         patch("contao_ai_cli.cli.helpers.click.prompt", return_value="5.abc") as prompt:
        assert resolve_token(None, False) == "5.abc"
    assert prompt.call_args.kwargs["hide_input"] is True
    assert prompt.call_args.kwargs["err"] is True


def test_no_terminal_and_no_token_explains_both_ways():
    with patch("contao_ai_cli.cli.helpers.stdin_is_console", return_value=False):
        with pytest.raises(click.UsageError) as e:
            resolve_token(None, False)
    assert "--token-stdin" in str(e.value) and "terminal" in str(e.value)


def test_a_redirected_stdin_is_no_console_even_when_isatty_says_so():
    """Measured 2026-09-17: Git Bash `< /dev/null` reports isatty True; the prompt hung."""
    from contao_ai_cli.cli import helpers

    with patch.object(helpers.sys, "stdin") as stdin, patch.object(helpers.sys, "platform", "linux"):
        stdin.isatty.return_value = False
        assert helpers.stdin_is_console() is False
    with patch.object(helpers.sys, "stdin") as stdin, patch.object(helpers.sys, "platform", "win32"):
        stdin.isatty.return_value = True
        stdin.fileno.side_effect = OSError("not a real handle")
        assert helpers.stdin_is_console() is False


def test_get_console_mode_argtypes_are_set_for_a_64_bit_handle():
    """
    review 2026-09-17: HANDLE is a 64-bit pointer. Without an explicit argtypes,
    ctypes assumes the default (32-bit-int) signature for GetConsoleMode's first
    argument, which can silently truncate the handle on 64-bit Python.
    """
    import ctypes
    import sys

    if sys.platform != "win32":
        pytest.skip("ctypes.windll and msvcrt exist only on Windows")

    from contao_ai_cli.cli import helpers

    with patch.object(helpers.sys, "stdin") as stdin, patch.object(helpers.sys, "platform", "win32"), \
         patch("msvcrt.get_osfhandle", return_value=123456789012), \
         patch.object(ctypes.windll.kernel32, "GetConsoleMode", return_value=1) as get_mode:
        stdin.isatty.return_value = True
        stdin.fileno.return_value = 3
        assert helpers.stdin_is_console() is True

    assert get_mode.argtypes == [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
