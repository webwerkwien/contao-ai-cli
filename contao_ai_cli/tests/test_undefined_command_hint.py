"""
"Command is not defined" usually means the bundle on that server is older.

Measured against web.werk.wien on 2026-09-01, which sits on core v0.2.14:

    $ contao-ai-cli --session web-werk-wien page tree
    Command "contao:page:tree" is not defined. Did you mean one of these?

    $ contao-ai-cli --session web-werk-wien ext list
    There are no commands defined in the "contao:ai" namespace.

True, and it reads like a typo or a broken CLI. `health` on the same server
answers `Core v0.2.14 -> update available: v0.2.33` one command earlier — so
the CLI holds both numbers and simply never connects them to the failure.

🎯 Third occurrence of one shape in a day: a mistyped session name reported a
missing bundle, a missing extension reported a broken DCA, and an outdated
bundle reports an unknown command. Each answer accurate, each pointing away
from the cause.

The hint must not overreach. When the server already runs the newest bundle,
the command genuinely does not exist, and blaming the version would be the same
mistake wearing different clothes — so that case gets its own sentence.
"""
from contao_ai_cli.utils.contao_backend import ContaoBackend


NOT_DEFINED = 'Command "contao:page:tree" is not defined. Did you mean one of these?'
NO_NAMESPACE = 'There are no commands defined in the "contao:ai" namespace.'


class TestRecognisingTheFailure:
    def test_an_undefined_command_is_recognised(self):
        assert ContaoBackend.undefined_contao_command(NOT_DEFINED) == "contao:page:tree"

    def test_an_empty_namespace_is_recognised(self):
        assert ContaoBackend.undefined_contao_command(NO_NAMESPACE) == "contao:ai"

    def test_an_unrelated_error_is_not(self):
        assert ContaoBackend.undefined_contao_command("SQLSTATE[42S02]: table missing") is None

    def test_a_command_outside_the_contao_namespace_is_not(self):
        """Only this bundle's commands track its version. A missing
        `doctrine:foo` says nothing about contao-ai-core-bundle."""
        assert ContaoBackend.undefined_contao_command(
            'Command "doctrine:foo" is not defined.'
        ) is None


class TestTheHint:
    def test_an_older_bundle_is_named_with_both_versions(self):
        hint = ContaoBackend.version_hint("contao:page:tree", "v0.2.14", "v0.2.33")

        assert "v0.2.14" in hint
        assert "v0.2.33" in hint
        assert "contao:page:tree" in hint

    def test_the_newest_bundle_rules_the_version_out_instead(self):
        """
        The server is current, so the command really does not exist. Saying
        "your bundle is old" here would be the same failure this hint exists to
        remove — an accurate-sounding answer pointing the wrong way.
        """
        hint = ContaoBackend.version_hint("contao:page:tree", "v0.2.33", "v0.2.33")

        assert hint is not None
        assert "update" not in hint.lower()
        # It has to say the version was checked and excluded, or the reader
        # cannot tell this from "the CLI had no idea".
        assert "v0.2.33" in hint

    def test_a_newer_bundle_than_packagist_is_not_called_outdated(self):
        """A working copy ahead of the registry is not behind it."""
        hint = ContaoBackend.version_hint("contao:page:tree", "v0.2.40", "v0.2.33")

        assert "update" not in hint.lower()

    def test_an_unknown_installed_version_says_so_rather_than_guessing(self):
        hint = ContaoBackend.version_hint("contao:page:tree", None, "v0.2.33")

        assert hint is not None
        assert "v0.2.33" not in hint or "could not" in hint.lower()

    def test_an_unreachable_registry_still_names_what_is_installed(self):
        hint = ContaoBackend.version_hint("contao:page:tree", "v0.2.14", None)

        assert "v0.2.14" in hint

    def test_nothing_known_at_all_produces_no_hint(self):
        """Silence beats a sentence that carries no information."""
        assert ContaoBackend.version_hint("contao:page:tree", None, None) is None
