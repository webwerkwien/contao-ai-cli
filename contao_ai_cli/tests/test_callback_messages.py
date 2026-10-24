"""An error shows what the DCA callbacks told the editor (core-bundle v1.6.0).

The core answers Contao's messages (`Message::addError()` …) as `messages`. A
success prints its whole JSON; an error printed only `message`, and a refusing
callback's reason was lost — measured on Contao 6.0.
"""
import json

from contao_ai_cli.utils.contao_backend import ContaoBackend


def test_an_error_lists_the_callbacks_messages():
    stdout = json.dumps({
        "status": "error",
        "message": "InvalidArgumentException: tl_page.onsubmit refused. Nothing was written.",
        "code": 1,
        "messages": [
            {"type": "error", "text": "Titel abgelehnt"},
            {"type": "info", "text": " Sitemap wird neu erstellt. "},
            {"type": "error", "text": "  "},
            "kaputt",
        ],
    })

    assert ContaoBackend._explain_failure(stdout, "") == (
        "InvalidArgumentException: tl_page.onsubmit refused. Nothing was written."
        "\nContao error: Titel abgelehnt"
        "\nContao info: Sitemap wird neu erstellt."
    )


def test_without_messages_the_message_stands_alone():
    stdout = json.dumps({"status": "error", "message": "Page not found: 9", "code": 1})

    assert ContaoBackend._explain_failure(stdout, "") == "Page not found: 9"


def test_messages_that_are_no_list_are_ignored():
    stdout = json.dumps({"status": "error", "message": "x", "messages": "kaputt"})

    assert ContaoBackend._explain_failure(stdout, "") == "x"
