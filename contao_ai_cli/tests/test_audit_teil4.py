"""
The remaining findings of the 2026-09-02 audit, pinned.

v0.14.0 closed the SSH option injection and the passwords. This covers what was
left open then and fixed in v0.15.0: M-2, M-1, C-1, H-1, M-4 and the reported
host key. M-3 lives in test_bulk_update.py, next to the test it had to invert.
"""
import json
import os
import stat
import sys

import click
import pytest

from contao_ai_cli.core.contao_ops import join_args, build_set_args
from contao_ai_cli.core import session as session_mod
from contao_ai_cli.core.backend_bridge import BackendBridgeClient, BridgeError, _NoRedirect
from contao_ai_cli.cli.cli_connect import _host_key_notice


class TestM2QuotedValuesSurvive:
    """
    `" ".join(cmd.split())` normalised the whole command after quoting, so a
    value containing a newline or two spaces was silently rewritten and the
    command still answered `ok`. Not a security hole — a data loss in the
    everyday write path.
    """

    def test_a_newline_in_a_value_survives(self):
        cmd = join_args("contao:news:update", 42,
                        build_set_args({"text": "Zeile1\nZeile2"}), "--no-interaction")

        assert "Zeile1\nZeile2" in cmd

    def test_repeated_spaces_survive(self):
        cmd = join_args("contao:news:update", 42,
                        build_set_args({"headline": "zwei  Leerzeichen"}), "--no-interaction")

        assert "zwei  Leerzeichen" in cmd

    def test_empty_parts_leave_no_double_space(self):
        # This is what the normalisation was there for. Dropping empties before
        # joining removes the reason it existed, rather than cleaning up after it.
        cmd = join_args("contao:user:update", "'alice'", build_set_args({}), "--no-interaction")

        assert cmd == "contao:user:update 'alice' --no-interaction"
        assert "  " not in cmd

    def test_no_module_normalises_a_built_command_any_more(self):
        """
        The shape, not the four instances — a fifth would be the same bug.

        ⚠️ Comments and strings are stripped first, and that is not tidiness.
        The fix for M-2 documents the old form in a docstring (*'used to tidy it
        with " ".join(cmd.split())'*), because a fix without its reason is a line
        nobody dares touch later. A scan reading that text fails on the very file
        that was repaired — which is exactly what happened on the first run.
        The core bundle's WritePathTest hit this too and solved it the same way.
        """
        import io
        import pathlib
        import tokenize

        core = pathlib.Path(join_args.__module__.replace(".", "/")).parent
        offenders = []
        checked = 0

        for path in sorted(core.glob("*.py")):
            checked += 1
            code = []
            with io.open(path, encoding="utf-8") as fh:
                for tok in tokenize.generate_tokens(fh.readline):
                    if tok.type in (tokenize.COMMENT, tokenize.STRING):
                        continue
                    code.append(tok.string)
            joined = " ".join(code)

            # 🎯 Match on what SURVIVES the stripping. The first version of this
            # looked for `" ".join(cmd.split())` — but `" "` is a STRING token
            # and had just been removed, so the pattern could never appear and
            # the test passed no matter what. It only came out because the
            # mutation check put the old form back and the test stayed green.
            # A scan that cannot fail is not a scan.
            if "join ( cmd . split" in joined:
                offenders.append(path.name)

        assert checked >= 10, f"the scan only saw {checked} modules"
        assert offenders == [], f"a command is normalised after quoting again: {offenders}"


class TestM1SessionPermissions:
    def test_an_existing_file_gets_its_mode_tightened(self, tmp_path):
        # os.open()'s mode applies only on creation, so a file that was once
        # 0644 kept 0644 while a bearer token was written into it.
        path = tmp_path / "session.json"
        path.write_text("{}", encoding="utf-8")
        os.chmod(path, 0o644)

        session_mod.save_session({"bridge_token": "5.geheim"}, str(path))

        mode = stat.S_IMODE(os.stat(path).st_mode)
        if os.name == "nt":
            # Windows does not carry POSIX modes; the call must simply not fail.
            assert json.loads(path.read_text(encoding="utf-8"))["bridge_token"] == "5.geheim"
        else:
            assert mode == 0o600, f"session file left at {oct(mode)}"

    def test_saving_still_works_when_chmod_is_impossible(self, tmp_path, monkeypatch):
        # Best-effort on purpose: refusing to save a session over a failed chmod
        # would be the worse outcome.
        monkeypatch.setattr(os, "chmod", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
        path = tmp_path / "session.json"

        session_mod.save_session({"host": "example.com"}, str(path))

        assert json.loads(path.read_text(encoding="utf-8"))["host"] == "example.com"


class TestC1BridgeUrl:
    @pytest.mark.parametrize("url", [
        "http://example.com",
        "http://localhost:8000",
        "ftp://example.com",
    ])
    def test_a_non_https_bridge_url_is_refused(self, url):
        with pytest.raises(BridgeError, match="non-https"):
            BackendBridgeClient(url, "5.geheim")

    def test_https_is_accepted(self):
        client = BackendBridgeClient("https://c5.example.com/", "5.geheim")

        assert client.base_url == "https://c5.example.com"

    def test_a_local_http_bridge_needs_an_explicit_opt_in(self):
        client = BackendBridgeClient("http://localhost:8000", "5.geheim", allow_insecure=True)

        assert client.base_url == "http://localhost:8000"

    def test_a_url_without_a_host_is_refused(self):
        with pytest.raises(BridgeError, match="no host"):
            BackendBridgeClient("https:///macro", "5.geheim")

    def test_redirects_are_refused_rather_than_followed(self):
        # urllib keeps the Authorization header across a redirect, including to
        # another host — so following one hands the bearer token away.
        with pytest.raises(BridgeError, match="redirected"):
            _NoRedirect().redirect_request(
                None, None, 302, "Found", {}, "https://elsewhere.example/macro"
            )

    def test_the_client_installs_the_no_redirect_opener(self):
        client = BackendBridgeClient("https://c5.example.com", "5.geheim")

        assert any(isinstance(h, _NoRedirect) for h in client._opener.handlers)


class TestH10HostKeyNotice:
    def test_a_first_contact_is_reported(self):
        stderr = "Warning: Permanently added 'c5.axeltest.at' (ED25519) to the list of known hosts."

        notice = _host_key_notice(stderr)

        assert notice is not None
        assert "c5.axeltest.at" in notice
        assert not notice.startswith("Warning: ")

    def test_a_known_host_produces_no_notice(self):
        assert _host_key_notice("") is None
        assert _host_key_notice("some unrelated stderr\n") is None

    def test_it_matches_the_stable_middle_of_the_sentence(self):
        # Matched on "Permanently added" rather than the full wording, so a
        # reworded warning still registers as "a key was accepted".
        assert _host_key_notice("Permanently added host to known hosts") is not None
