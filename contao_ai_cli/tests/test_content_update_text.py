"""`content update --text` as on `content create`.

Live on web.werk.wien on 2026-09-17 (ConpAI 1.0, Nr. 60): translating four text elements
with `content update 256 --text '<p>…</p>'` failed with *"No such option '--text'"*,
although `content create` has had the shortcut all along. Nothing was written — click
refused before any server call — but the asymmetry costs a round trip per caller.
"""
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from contao_ai_cli.cli.cli_content import content_update_cmd


def _invoke(args):
    with patch("contao_ai_cli.cli.cli_content._require_core_bundle"), \
         patch("contao_ai_cli.cli.cli_content._get_backend", return_value=MagicMock()), \
         patch("contao_ai_cli.cli.cli_content.dispatch_update", return_value={"status": "ok"}) as dispatch:
        result = CliRunner().invoke(content_update_cmd, args, obj={})
    return result, dispatch


def test_text_is_a_shortcut_for_set_text():
    result, dispatch = _invoke(["256", "--text", "<p>Hello</p>", "--json"])

    assert result.exit_code == 0, result.output
    assert dispatch.call_args.args[5] == {"text": "<p>Hello</p>"}


def test_text_and_set_go_together():
    result, dispatch = _invoke(["258", "--set", "headline=The missing layer", "--text", "<p>x</p>", "--json"])

    assert result.exit_code == 0, result.output
    assert dispatch.call_args.args[5] == {"headline": "The missing layer", "text": "<p>x</p>"}


def test_an_explicit_set_text_wins_as_on_create():
    result, dispatch = _invoke(["1", "--set", "text=<p>set</p>", "--text", "<p>short</p>", "--json"])

    assert result.exit_code == 0, result.output
    assert dispatch.call_args.args[5] == {"text": "<p>set</p>"}


def test_nothing_to_change_is_still_refused():
    result, dispatch = _invoke(["1", "--json"])

    assert result.exit_code != 0
    dispatch.assert_not_called()
