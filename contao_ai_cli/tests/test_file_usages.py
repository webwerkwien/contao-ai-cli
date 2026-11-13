"""`file usages` passes the path and the --paths-only switch to contao:file:usages."""
from unittest.mock import MagicMock, patch

from contao_ai_cli.core.file import file_usages


def _run(paths_only: bool) -> str:
    backend = MagicMock()
    with patch("contao_ai_cli.core.file.run_json_or_raw", return_value={"status": "ok"}) as run:
        assert file_usages(backend, "files/a b.png", paths_only) == {"status": "ok"}
    return run.call_args.args[1]


def test_the_path_is_quoted():
    assert _run(False) == "contao:file:usages --path 'files/a b.png'"


def test_paths_only_is_passed_on():
    assert _run(True) == "contao:file:usages --path 'files/a b.png' --paths-only"
