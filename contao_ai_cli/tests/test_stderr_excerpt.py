"""A failed shell command shows the part of its stderr that explains it, without PHP start-up noise.

For most output that is the end. For a Composer problem report it is the whole problem
block minus the lines that explain nothing (v1.1.1, #63) -- see COMPOSER_53 below.

c5, 2026-09-19: `bundle update core` against backend-bundle v0.9.1 failed, and the
message showed an imagick.so start-up warning plus "./composer.json has been
updated" — the first 500 characters. Composer's reason (backend v0.9.1 requires
core <1.0) came later and was cut off.
"""
from unittest.mock import MagicMock, patch

import pytest

from contao_ai_cli.utils.contao_backend import (
    COMPOSER_EXCERPT_CHARS, STDERR_EXCERPT_CHARS, ContaoBackend, ContaoBackendError, stderr_excerpt,
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


# Measured 2026-10-03: `bundle install backend` on a Contao 5.3 installation. 2879
# characters without the imagick lines. The two reasons that matter -- symfony/clock
# held at 6.4 (line 9) and contao/core-bundle held at 5.3 (line 12) -- began 2460 and
# 1693 characters before the end, so the 1500-character tail kept neither. What it did
# keep were the lines about long-gone backend releases and the core constraint, which
# point at the wrong cause entirely.
COMPOSER_53 = """./composer.json has been updated
Running composer update webwerkwien/contao-ai-backend-bundle
Loading composer repositories with package information
Updating dependencies
Your requirements could not be resolved to an installable set of packages.

  Problem 1
    - Root composer.json requires webwerkwien/contao-ai-backend-bundle >=0.1 <2.0 -> satisfiable by webwerkwien/contao-ai-backend-bundle[v0.1.0, ..., v0.10.0].
    - symfony/ai-bundle v0.13.0 requires symfony/clock ^7.3|^8.0 -> found symfony/clock[v7.3.0, v7.3.8, v7.4.0, v7.4.8, v8.0.0, v8.0.8, v8.1.0] but the package is fixed to v6.4.30 (lock file version) by a partial update and that version does not match. Make sure you list it as an argument for the update command.
    - webwerkwien/contao-ai-backend-bundle[v0.1.0, ..., v0.1.5] require webwerkwien/contao-ai-core-bundle ^0.2 -> found webwerkwien/contao-ai-core-bundle[v0.2.0, ..., v0.2.38] but it conflicts with your root composer.json require (^1.0).
    - webwerkwien/contao-ai-backend-bundle v0.1.6 requires webwerkwien/contao-ai-core-bundle ^0.2.38 -> found webwerkwien/contao-ai-core-bundle[v0.2.38] but it conflicts with your root composer.json require (^1.0).
    - webwerkwien/contao-ai-backend-bundle v0.10.0 requires contao/core-bundle ^5.7 || ^6.0 -> found contao/core-bundle[5.7.0, ..., 5.7.13, 6.0.0, 6.0.1, 6.0.2] but the package is fixed to 5.3.51 (lock file version) by a partial update and that version does not match. Make sure you list it as an argument for the update command.
    - webwerkwien/contao-ai-backend-bundle[v0.2.0, ..., v0.3.0] require webwerkwien/contao-ai-core-bundle >=0.2.38 <1.0 -> found webwerkwien/contao-ai-core-bundle[v0.2.38, ..., v0.28.0] but it conflicts with your root composer.json require (^1.0).
    - webwerkwien/contao-ai-backend-bundle[v0.4.0, ..., v0.6.0] require webwerkwien/contao-ai-core-bundle >=0.4.0 <1.0 -> found webwerkwien/contao-ai-core-bundle[v0.4.0, ..., v0.28.0] but it conflicts with your root composer.json require (^1.0).
    - webwerkwien/contao-ai-backend-bundle[v0.7.0, ..., v0.7.1] require webwerkwien/contao-ai-core-bundle >=0.5.0 <1.0 -> found webwerkwien/contao-ai-core-bundle[v0.5.0, ..., v0.28.0] but it conflicts with your root composer.json require (^1.0).
    - webwerkwien/contao-ai-backend-bundle[v0.8.0, ..., v0.9.1] require webwerkwien/contao-ai-core-bundle >=0.6.0 <1.0 -> found webwerkwien/contao-ai-core-bundle[v0.6.0, ..., v0.28.0] but it conflicts with your root composer.json require (^1.0).
    - webwerkwien/contao-ai-backend-bundle[v0.9.2, ..., v0.9.3] require symfony/ai-bundle ^0.13 -> satisfiable by symfony/ai-bundle[v0.13.0].

Use the option --with-all-dependencies (-W) to allow upgrades, downgrades and removals for packages currently locked to specific versions.

Installation failed, reverting ./composer.json and ./composer.lock to their original content."""


def test_the_measured_composer_output_is_long_enough_to_have_been_cut():
    """The counter: if this fixture were short, the tests below would pass by accident."""
    assert len(COMPOSER_53) > STDERR_EXCERPT_CHARS + 1000


def test_composer_keeps_every_reason_in_the_problem_block():
    text = stderr_excerpt(IMAGICK + "\n" + COMPOSER_53)
    assert "symfony/clock[v7.3.0" in text and "fixed to v6.4.30" in text
    assert "contao/core-bundle ^5.7 || ^6.0" in text and "fixed to 5.3.51" in text
    assert text.endswith("to their original content.")


def test_composer_drops_lines_that_explain_nothing():
    """`-> satisfiable by` says that part is fine; progress lines say nothing at all."""
    text = stderr_excerpt(COMPOSER_53)
    assert "satisfiable by" not in text
    assert "Loading composer repositories" not in text
    assert "./composer.json has been updated" not in text
    assert text.startswith("Your requirements could not be resolved")
    # A known non-match: a reason line that mentions an older release stays.
    assert "v0.1.6 requires webwerkwien/contao-ai-core-bundle ^0.2.38" in text


def test_a_satisfiable_line_with_a_but_is_a_reason():
    block = ("Your requirements could not be resolved to an installable set of packages.\n\n"
             "  Problem 1\n"
             "    - a/b 1.0 requires c/d ^2 -> satisfiable by c/d[2.0] but these were not loaded, "
             "likely because it conflicts with another require.\n")
    assert "these were not loaded" in stderr_excerpt(block)


def test_an_oversized_problem_block_keeps_its_head_and_its_end():
    reasons = "\n".join(f"    - vendor/pkg{i} 1.0 requires x/y ^{i} -> found x/y[{i}.0] but it conflicts "
                        f"with your root composer.json require (^0)." + " pad" * 30 for i in range(80))
    block = ("Your requirements could not be resolved to an installable set of packages.\n\n"
             "  Problem 1\n" + reasons +
             "\n\nInstallation failed, reverting ./composer.json and ./composer.lock to their original content.")
    text = stderr_excerpt(block)
    assert len(text) <= COMPOSER_EXCERPT_CHARS + 200
    assert "vendor/pkg0 1.0" in text, "the first reasons stay"
    assert text.endswith("to their original content."), "and so does the verdict"
    assert "…" in text
    assert "vendor/pkg40 1.0" not in text, "the middle goes"


def test_a_single_reason_longer_than_the_room_is_cut_not_dropped():
    """Review 2026-10-03: one 6000-character reason vanished entirely, the marker stood in for it."""
    block = ("Your requirements could not be resolved to an installable set of packages.\n\n"
             "  Problem 1\n"
             "    - vendor/giant 1.0 requires x/y ^9 -> found x/y[" + "9.0, " * 1200 + "] but it conflicts.\n\n"
             "Installation failed, reverting ./composer.json and ./composer.lock to their original content.")
    text = stderr_excerpt(block)
    assert "vendor/giant 1.0 requires x/y ^9" in text
    assert len(text) <= COMPOSER_EXCERPT_CHARS + 200
    assert text.endswith("to their original content.")


def test_the_real_path_carries_stderr_into_the_bundle_answer():
    """Review 2026-10-03 (rule 25): the other test builds the error itself. This one lets
    run_raw raise it, through composer_bundle, into install_bundle's answer."""
    from contao_ai_cli.core import bundles
    backend = ContaoBackend.__new__(ContaoBackend)
    backend.contao_root = "/var/www"
    backend.php_path = "php"
    with patch.object(ContaoBackend, "_ssh_args", return_value=["ssh"]), \
         patch.object(ContaoBackend, "run", return_value={"returncode": 0, "stdout": "", "stderr": ""}), \
         patch.object(bundles, "get_installed_package_versions", return_value={bundles.BACKEND_BUNDLE: None}), \
         patch.object(bundles, "detect_contao_manager", return_value={"available": True, "phar_path": "p"}), \
         patch("contao_ai_cli.utils.contao_backend.subprocess.run",
               return_value=MagicMock(returncode=2, stdout="", stderr=IMAGICK + "\n" + COMPOSER_53)) as run:
        result = bundles.install_bundle(backend, "backend", "install")
    assert "composer require" in run.call_args[0][0][-1], "the composer call itself went through run_raw"
    assert result["status"] == "error"
    assert "fixed to v6.4.30" in result["message"]
    assert "satisfiable by" in result["stderr"] and "imagick" not in result["stderr"]


def test_non_composer_output_still_keeps_its_end():
    text = stderr_excerpt("Problem with the database\n" + "x" * 5000 + "\nthe verdict")
    assert text.startswith("…") and text.endswith("the verdict")


def test_the_error_carries_the_full_cleaned_stderr():
    """An agent should not depend on a cut that has to guess what matters."""
    backend = ContaoBackend.__new__(ContaoBackend)
    backend.contao_root = "/var/www"
    with patch.object(ContaoBackend, "_ssh_args", return_value=["ssh"]), \
         patch("contao_ai_cli.utils.contao_backend.subprocess.run",
               return_value=MagicMock(returncode=2, stdout="", stderr=IMAGICK + "\n" + COMPOSER_53)):
        with pytest.raises(ContaoBackendError) as e:
            backend.run_raw("composer require x")
    assert e.value.stderr is not None
    assert "imagick" not in e.value.stderr
    assert "./composer.json has been updated" in e.value.stderr, "full means full, progress lines included"
    assert "satisfiable by" in e.value.stderr


def test_a_failed_bundle_install_reports_the_full_stderr():
    from contao_ai_cli.core import bundles
    backend = MagicMock()
    backend.run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    error = ContaoBackendError("Shell command failed (exit 2). Stderr: cut", stderr="the whole story")
    with patch.object(bundles, "get_installed_package_versions", return_value={bundles.BACKEND_BUNDLE: None}), \
         patch.object(bundles, "detect_contao_manager", return_value={"available": True, "phar_path": "p"}), \
         patch.object(bundles, "composer_bundle", side_effect=error):
        result = bundles.install_bundle(backend, "backend", "install")
    assert result["status"] == "error"
    assert result["stderr"] == "the whole story"
    assert "cut" in result["message"]


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
