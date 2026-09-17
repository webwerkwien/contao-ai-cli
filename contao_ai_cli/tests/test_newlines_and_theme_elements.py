"""Two findings from the ConpAI 1.0 site build on web.werk.wien, 2026-09-17.

Nr. 65: `file write` turned LF into CRLF on Windows. The content went into a temp file
opened in text mode, which writes the platform's line ending, so site.css arrived with
CRLF. `template write` had the same temp file, and both read `@file` in text mode,
which turned a file's own CRLF into LF. Content now travels byte for byte.

Nr. 68: `layout module-add` took only a number. Since Contao 5.7 a layout also holds a
theme's content elements, stored as `content-<id>`; the site's header and footer are
two of them (core-bundle v0.24.0 checks the element and its theme).
"""
import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_file import file_write_cmd
from contao_ai_cli.cli.cli_layout import layout_module_add_cmd
from contao_ai_cli.core.file import file_write
from contao_ai_cli.core.layout import layout_module
from contao_ai_cli.core.template import template_write


def _backend() -> tuple[MagicMock, dict]:
    uploaded = {}
    backend = MagicMock()
    backend.contao_root = "/web"

    def scp_upload(local, remote):
        with open(local, "rb") as f:
            uploaded["bytes"] = f.read()
        return {"returncode": 0}

    backend.scp_upload.side_effect = scp_upload
    backend.run.return_value = {"stdout": '{"status":"ok"}', "returncode": 0, "stderr": ""}
    backend.undefined_command_hint.return_value = ""
    return backend, uploaded


def test_file_write_sends_line_endings_unchanged():
    backend, uploaded = _backend()
    file_write(backend, "files/site.css", "a {}\nb {}\r\nc {}\n")
    assert uploaded["bytes"] == b"a {}\nb {}\r\nc {}\n"


def test_template_write_sends_line_endings_unchanged():
    backend, uploaded = _backend()
    template_write(backend, "override", "content_element/text", "{{ a }}\n{{ b }}\n")
    assert uploaded["bytes"] == b"{{ a }}\n{{ b }}\n"


def test_an_at_file_is_read_byte_for_byte(tmp_path):
    local = tmp_path / "site.css"
    local.write_bytes("a {}\nb {} /* ü */\r\n".encode("utf-8"))
    backend, uploaded = _backend()

    with patch("contao_ai_cli.cli.cli_file._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_file._get_backend", return_value=backend):
        result = CliRunner().invoke(file_write_cmd, ["--path", "files/site.css", "--content", f"@{local}", "--json"], obj={})

    assert result.exit_code == 0, result.output
    assert uploaded["bytes"] == local.read_bytes()


def test_a_theme_content_element_is_passed_as_content_id():
    backend, _ = _backend()
    layout_module(backend, 2, "content-317", "header")
    assert backend.run.call_args.args[0] == "contao:layout:module --layout 2 --module content-317 --col header"


def test_module_add_accepts_content_id_and_refuses_anything_else():
    backend, _ = _backend()
    with patch("contao_ai_cli.cli.cli_layout._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_layout._get_backend", return_value=backend):
        ok = CliRunner().invoke(layout_module_add_cmd, ["--layout", "2", "--module", "content-318", "--col", "footer", "--json"], obj={})
        bad = CliRunner().invoke(layout_module_add_cmd, ["--layout", "2", "--module", "header; rm", "--col", "footer"], obj={})

    assert ok.exit_code == 0, ok.output
    assert json.loads(ok.stdout)["status"] == "ok"
    assert "--module content-318" in backend.run.call_args_list[0].args[0]
    assert bad.exit_code == 2
    assert backend.run.call_count == 1
