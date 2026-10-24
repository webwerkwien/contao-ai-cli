"""
Theme export/import and example websites (v1.10.0, core-bundle v1.9.0).

The server runs Contao's theme manager; this side moves files and asks. What is pinned
here: the files go to system/tmp and are removed again, nothing is imported without a
yes, and the next steps fit the mode. The server side ran against Contao 5.3, 5.7 and 6.0.
"""
import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from contao_ai_cli.core import theme_archive


def backend(*answers):
    """A backend whose console answers come in order; raw commands are recorded."""
    b = MagicMock()
    b.contao_root = "/var/www/site"
    b.run.side_effect = [{"stdout": json.dumps(a), "returncode": 0 if a.get("status") != "error" else 1} for a in answers]
    b.run_raw.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
    b.scp_upload.return_value = {"returncode": 0}
    b.undefined_command_hint.return_value = ""

    def download(remote, local, *a):
        with open(local, "wb") as f:
            f.write(b"PK")
        return {"returncode": 0}

    b.scp_download.side_effect = download
    return b


def raw_commands(b):
    return [c[0][0] for c in b.run_raw.call_args_list]


class TestExport:
    def test_the_archive_is_downloaded_and_removed_on_the_server(self, tmp_path):
        b = backend({"status": "ok", "file": "system/tmp/ab12.cto", "size": 2, "theme": "Demo Theme", "note": "n"})
        target = tmp_path / "out.cto"
        result = theme_archive.theme_export(b, 1, str(target))

        assert result["status"] == "ok" and result["size"] == 2
        assert b.scp_download.call_args[0][0] == "/var/www/site/system/tmp/ab12.cto"
        assert "rm -f system/tmp/ab12.cto" in raw_commands(b)

    def test_an_existing_file_of_the_default_name_is_not_overwritten(self, tmp_path, monkeypatch):
        """In a draft a second export replaced the first without a word."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "Demo-Theme.cto").write_bytes(b"earlier")
        b = backend({"status": "ok", "file": "system/tmp/ab12.cto", "size": 2, "theme": "Demo Theme", "note": "n"})
        with pytest.raises(theme_archive.ArchiveError, match="exists here already"):
            theme_archive.theme_export(b, 1)
        assert (tmp_path / "Demo-Theme.cto").read_bytes() == b"earlier"
        assert "rm -f system/tmp/ab12.cto" in raw_commands(b), "the server's copy goes either way"

    def test_the_last_json_line_is_the_answer(self):
        b = MagicMock()
        b.undefined_command_hint.return_value = ""
        result = {"stdout": 'PHP Warning: imagick\n{"status":"ok","n":1}', "returncode": 0}
        assert theme_archive._answer(b, result) == {"status": "ok", "n": 1}

    def test_a_missing_command_carries_the_version_hint(self):
        b = MagicMock()
        b.undefined_command_hint.return_value = "\n  core-bundle v1.8.1 is installed; v1.9.0 has it."
        with pytest.raises(theme_archive.ArchiveError, match="v1.9.0 has it"):
            theme_archive._answer(b, {"stdout": "", "stderr": 'Command "contao:theme:export" is not defined.', "returncode": 1})

    def test_an_unexpected_path_is_not_downloaded(self, tmp_path):
        b = backend({"status": "ok", "file": "../../etc/passwd", "theme": "x"})
        with pytest.raises(theme_archive.ArchiveError, match="Unexpected export path"):
            theme_archive.theme_export(b, 1, str(tmp_path / "x.cto"))
        b.scp_download.assert_not_called()


class TestImportCommand:
    PREVIEW = {"status": "preview", "themes": ["Demo"], "tables": {"tl_module": 4}, "overwrites": ["files/a.jpg"],
               "new_files": 1, "missing_fields": {}, "example_websites": [], "existing_names": [], "lost_theme_elements": 0}

    def invoke(self, monkeypatch, tmp_path, args, *answers, console=False, answer=None):
        from contao_ai_cli.cli import cli_theme, helpers

        b = backend(*answers)
        monkeypatch.setattr(cli_theme, "_get_backend", lambda path: b)
        monkeypatch.setattr(cli_theme, "_require_core_bundle", lambda ctx, what: None)
        monkeypatch.setattr(helpers, "stdin_is_console", lambda: console)
        monkeypatch.setattr(helpers, "ask_yes_no", lambda q, default=False: answer)
        archive = tmp_path / "demo.cto"
        archive.write_bytes(b"PK")
        result = CliRunner().invoke(cli_theme.theme, ["import", str(archive), *args], obj={"session": None, "as_json": True})
        return result, b

    def test_without_a_yes_the_preview_is_the_answer(self, monkeypatch, tmp_path):
        result, b = self.invoke(monkeypatch, tmp_path, [], self.PREVIEW)
        out = json.loads(result.output)
        assert out["status"] == "preview" and out["imported"] is False
        assert b.run.call_count == 1
        assert "--confirm" not in b.run.call_args[0][0]

    def test_yes_imports_and_the_upload_is_removed(self, monkeypatch, tmp_path):
        result, b = self.invoke(monkeypatch, tmp_path, ["--yes"], self.PREVIEW,
                                {"status": "ok", "theme_ids": [7], "messages": []})
        assert result.exit_code == 0, result.output
        remote = b.scp_upload.call_args[0][1]
        assert remote.startswith("/var/www/site/system/tmp/contao-ai-") and remote.endswith(".cto")
        assert b.run.call_args[0][0].endswith(" --confirm")
        # The exact file, not a prefix a neighbouring rm would satisfy too.
        relative = remote.removeprefix("/var/www/site/")
        assert f"rm -f {relative}" in raw_commands(b)
        assert "cache clear" in json.loads(result.output)["nextSteps"][0]["command"]

    def test_a_failed_upload_leaves_nothing_behind(self, tmp_path):
        b2 = backend()
        b2.scp_upload.return_value = {"returncode": 1, "stderr": "connection lost"}
        archive = tmp_path / "x.cto"
        archive.write_bytes(b"PK")
        with pytest.raises(theme_archive.ArchiveError, match="Upload failed"):
            with theme_archive.Upload(b2, str(archive), theme_archive.THEME_EXTENSIONS):
                pass
        relative = b2.scp_upload.call_args[0][1].removeprefix("/var/www/site/")
        assert f"rm -f {relative}" in raw_commands(b2)
        # The name core-bundle gives an extracted example website (EXTRACTED_SUFFIX).
        assert f"rm -f {relative.removesuffix('.cto')}-example.sql" in raw_commands(b2)

    def test_a_wrong_file_type_is_refused_before_the_upload(self, monkeypatch, tmp_path):
        from contao_ai_cli.cli import cli_theme

        b = backend()
        monkeypatch.setattr(cli_theme, "_get_backend", lambda path: b)
        monkeypatch.setattr(cli_theme, "_require_core_bundle", lambda ctx, what: None)
        sql = tmp_path / "site.sql"
        sql.write_text("INSERT")
        result = CliRunner().invoke(cli_theme.theme, ["import", str(sql)], obj={"session": None, "as_json": True})
        assert result.exit_code != 0 and ".cto" in result.output
        b.scp_upload.assert_not_called()

    def test_a_person_at_a_terminal_decides(self, monkeypatch, tmp_path):
        result, b = self.invoke(monkeypatch, tmp_path, [], self.PREVIEW, console=True, answer=False)
        assert json.loads(result.output)["imported"] is False
        assert b.run.call_count == 1


class TestExampleWebsiteCommand:
    PREVIEW = {"status": "preview", "file": "system/tmp/x.sql", "mode": "data", "statements": 2,
               "tables": ["tl_page", "tl_user"], "truncates": 30, "user_rows": 1,
               "existing_admins": ["admin"], "needs_admin_decision": True}

    def invoke(self, monkeypatch, tmp_path, args, *answers):
        from contao_ai_cli.cli import cli_example_website, helpers

        b = backend(*answers)
        monkeypatch.setattr(cli_example_website, "_get_backend", lambda path: b)
        monkeypatch.setattr(cli_example_website, "_require_core_bundle", lambda ctx, what: None)
        monkeypatch.setattr(helpers, "stdin_is_console", lambda: False)
        sql = tmp_path / "x.sql"
        sql.write_text("INSERT INTO `tl_page` VALUES (1);\n")
        result = CliRunner().invoke(cli_example_website.example_website, ["import", str(sql), *args],
                                    obj={"session": None, "as_json": True})
        return result, b

    def test_there_is_no_default_mode(self, monkeypatch, tmp_path):
        result, b = self.invoke(monkeypatch, tmp_path, ["--yes"])
        assert result.exit_code == 2 and "--mode" in result.output
        b.scp_upload.assert_not_called()

    def test_without_a_yes_nothing_is_imported(self, monkeypatch, tmp_path):
        """In a draft the command that can empty the database had no test for it."""
        result, b = self.invoke(monkeypatch, tmp_path, ["--mode", "data", "--admins", "existing"], self.PREVIEW)
        out = json.loads(result.output)
        assert out["status"] == "preview" and out["imported"] is False
        assert b.run.call_count == 1
        assert "--confirm" not in b.run.call_args[0][0]

    def test_existing_admins_need_a_decision_even_with_yes(self, monkeypatch, tmp_path):
        result, b = self.invoke(monkeypatch, tmp_path, ["--mode", "data", "--yes"], self.PREVIEW)
        assert result.exit_code == 1
        assert "--admins both" in json.loads(result.output)["next"]
        assert b.run.call_count == 1

    @pytest.mark.parametrize("mode, steps", [
        ("full", ["contao migrate", "contao filesync", "cache clear"]),
        ("data", ["contao filesync", "cache clear"]),
        ("data_no_truncate", ["cache clear"]),
    ])
    def test_the_next_steps_fit_the_mode(self, monkeypatch, tmp_path, mode, steps):
        done = {"status": "ok", "mode": mode, "backup": "backup__20261015090000.sql.gz", "backup_note": "n",
                "statements": 2, "admins": {"kept": ["admin"], "removed": ["demo"], "imported": []}, "messages": []}
        result, b = self.invoke(monkeypatch, tmp_path, ["--mode", mode, "--admins", "existing", "--yes"],
                                {**self.PREVIEW, "mode": mode}, done)
        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert [s["command"].replace("contao-ai-cli ", "") for s in out["nextSteps"]] == steps
        assert "--admins=existing" in b.run.call_args[0][0] and b.run.call_args[0][0].endswith("--confirm")
