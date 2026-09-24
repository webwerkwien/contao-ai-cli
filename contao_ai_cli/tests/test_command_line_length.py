"""
The Windows command-line cap, measured where Windows measures it.

The first version of the `--set-file` guard (issue #55) checked
`len(shlex.quote(value)) > 32000` on each value on its way in. A review on
2026-09-24 showed that this measures the wrong thing, and the three cases below
are the ones it waved through — each verified by an actual process start on
Windows 11:

    30000 x `x` + 1600 x `"`        quoted 31602   list2cmdline 33350   WinError 206
    29000 x `x` + 1000 x `\\"`       quoted 31002   list2cmdline 33150   WinError 206
    two --set-file values, 20000    quoted 20000   list2cmdline 40158   WinError 206

Two reasons: `subprocess` builds the real line with `list2cmdline`, which escapes
every `"` as `\\"`, and the cap is on the whole line, so several values add up.
An HTML block with 1600 quotes in 30000 characters is ordinary markup.

Left unguarded, the `OSError` fell through to the top-level handler in `main()`,
which treats whatever reaches it as a defect and writes an error report — for a
limit we knew about.
"""
import shlex
import subprocess
from unittest.mock import patch

import pytest

from contao_ai_cli.utils.contao_backend import (
    WINDOWS_COMMAND_LINE_LIMIT, ContaoBackend, ContaoBackendError,
)


def backend():
    b = ContaoBackend.__new__(ContaoBackend)
    b.host, b.user, b.port = "example.org", "site", 22
    b.contao_root, b.php_path, b.key_path = "/var/www/site", "php", None
    b._ssh_bin = "ssh"
    return b


def set_args(*values):
    return " ".join(f"--set {shlex.quote(f'f{i}={v}')}" for i, v in enumerate(values))


class TestTheGuardMeasuresTheWholeLine:
    @pytest.mark.parametrize("label, values", [
        ("quotes in the markup", ("x" * 30_000 + '"' * 1_600,)),
        ("escaped quotes", ("x" * 29_000 + '\\"' * 1_000,)),
        ("two values that each fit", ("y" * 20_000, "z" * 20_000)),
    ])
    def test_the_cases_the_per_value_check_let_through(self, label, values):
        with patch("contao_ai_cli.utils.contao_backend.sys.platform", "win32"), \
             patch("contao_ai_cli.utils.contao_backend.subprocess.run") as run:
            with pytest.raises(ContaoBackendError) as e:
                backend().run(f"contao:page:update 1 {set_args(*values)}")
        run.assert_not_called()
        assert "too long for Windows" in str(e.value)
        assert "Nothing was sent" in str(e.value)

    def test_those_cases_really_do_exceed_the_cap(self):
        """The counter. Without it the test above could be passing for any reason."""
        for values in (("x" * 30_000 + '"' * 1_600,), ("y" * 20_000, "z" * 20_000)):
            cmd = f"cd /var/www/site && php bin/console contao:page:update 1 {set_args(*values)}"
            line = subprocess.list2cmdline(backend()._ssh_args() + [cmd])
            assert len(line) > WINDOWS_COMMAND_LINE_LIMIT
            # and the discarded per-value check would have said yes to all of them
            assert all(len(shlex.quote(v)) <= WINDOWS_COMMAND_LINE_LIMIT for v in values)

    def test_an_ordinary_command_passes(self):
        """The known non-match: a guard that refuses everything passes the tests above."""
        with patch("contao_ai_cli.utils.contao_backend.sys.platform", "win32"), \
             patch("contao_ai_cli.utils.contao_backend.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "{}"
            run.return_value.stderr = ""
            backend().run("contao:page:update 1 --set title=Home")
        run.assert_called_once()

    def test_run_raw_is_guarded_too(self):
        """Both entry points build a command line; guarding one would be half a guard."""
        with patch("contao_ai_cli.utils.contao_backend.sys.platform", "win32"), \
             patch("contao_ai_cli.utils.contao_backend.subprocess.run") as run:
            with pytest.raises(ContaoBackendError):
                backend().run_raw("echo " + "x" * 40_000)
        run.assert_not_called()

    def test_there_is_no_such_limit_off_windows(self):
        """POSIX ARG_MAX is around 2 MB; refusing at 32000 there would invent a fault."""
        with patch("contao_ai_cli.utils.contao_backend.sys.platform", "linux"), \
             patch("contao_ai_cli.utils.contao_backend.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "{}"
            run.return_value.stderr = ""
            backend().run("contao:page:update 1 " + set_args("x" * 40_000))
        run.assert_called_once()
