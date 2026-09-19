"""A failed shell command shows the end of its stderr, without PHP start-up noise.

c5, 2026-09-19: `bundle update core` against backend-bundle v0.9.1 failed, and the
message showed an imagick.so start-up warning plus "./composer.json has been
updated" — the first 500 characters. Composer's reason (backend v0.9.1 requires
core <1.0) came later and was cut off.
"""
from unittest.mock import MagicMock, patch

import pytest

from contao_ai_cli.utils.contao_backend import (
    STDERR_EXCERPT_CHARS, ContaoBackend, ContaoBackendError, stderr_excerpt,
)

IMAGICK = ("PHP Warning:  PHP Startup: Unable to load dynamic library 'imagick.so' (tried: "
           "/opt/php-8.4/lib/php/extensions/no-debug-non-zts-20240924/imagick.so (libMagickWand-7.Q16HDRI.so.10: "
           "cannot open shared object file: No such file or directory), /opt/php-8.4/lib/php/extensions/"
           "no-debug-non-zts-20240924/imagick.so.so (/opt/php-8.4/lib/php/extensions/no-debug-non-zts-20240924/"
           "imagick.so.so: cannot open shared object file: No such file or directory)) in Unknown on line 0")
COMPOSER = """./composer.json has been updated
Running composer update webwerkwien/contao-ai-core-bundle
Your requirements could not be resolved to an installable set of packages.

  Problem 1
    - webwerkwien/contao-ai-backend-bundle v0.9.1 requires webwerkwien/contao-ai-core-bundle >=0.6.0 <1.0 -> found webwerkwien/contao-ai-core-bundle[v0.6.0, ..., v0.28.0] but it conflicts with your root composer.json require (^1.0).

Installation failed, reverting ./composer.json and ./composer.lock to their original content."""


def test_startup_noise_is_dropped_and_the_reason_kept():
    text = stderr_excerpt(IMAGICK + "\n" + IMAGICK + "\n" + COMPOSER)
    assert "imagick" not in text
    assert "requires webwerkwien/contao-ai-core-bundle >=0.6.0 <1.0" in text
    assert text.endswith("to their original content.")


def test_long_output_keeps_its_end():
    text = stderr_excerpt("x" * 5000 + "\nthe verdict")
    assert text.startswith("…")
    assert text.endswith("the verdict")
    assert len(text) == STDERR_EXCERPT_CHARS + 1


def test_empty_stderr():
    assert stderr_excerpt("") == ""
    assert stderr_excerpt(None) == ""


def test_other_start_up_noise_and_a_fatal_error():
    assert stderr_excerpt('PHP Warning:  Module "imagick" is already loaded in Unknown on line 0\nreal') == "real"
    fatal = "PHP Fatal error:  PHP Startup: Unable to start the extension in Unknown on line 0"
    assert stderr_excerpt(fatal) == fatal, "a fatal start-up error is a reason, not noise"


def test_crlf_line_endings():
    assert stderr_excerpt(IMAGICK + "\r\nreal error\r\n") == "real error"


def test_only_noise_says_so_instead_of_an_empty_message():
    backend = ContaoBackend.__new__(ContaoBackend)
    backend.contao_root = "/var/www"
    with patch.object(ContaoBackend, "_ssh_args", return_value=["ssh"]), \
         patch("contao_ai_cli.utils.contao_backend.subprocess.run",
               return_value=MagicMock(returncode=1, stdout="", stderr=IMAGICK)):
        with pytest.raises(ContaoBackendError) as e:
            backend.run_raw("mkdir x")
    assert str(e.value.message) == "Shell command failed (exit 1). No output from the server."


def test_console_failure_without_json_uses_the_same_excerpt():
    assert ContaoBackend._explain_failure("", IMAGICK + "\nSQLSTATE[HY000] [2002] Connection refused") \
        == "Stderr: SQLSTATE[HY000] [2002] Connection refused"


def test_run_raw_error_message_carries_the_reason():
    backend = ContaoBackend.__new__(ContaoBackend)
    backend.contao_root = "/var/www"
    with patch.object(ContaoBackend, "_ssh_args", return_value=["ssh"]), \
         patch("contao_ai_cli.utils.contao_backend.subprocess.run",
               return_value=MagicMock(returncode=2, stdout="", stderr=IMAGICK + "\n" + COMPOSER)):
        with pytest.raises(ContaoBackendError) as e:
            backend.run_raw("composer require x")
    assert "conflicts with your root composer.json require (^1.0)" in str(e.value.message)
    assert "imagick" not in str(e.value.message)
