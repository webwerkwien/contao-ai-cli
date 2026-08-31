"""
The form generator, write half — the last content module that was read-only.

`form list` and `form fields` have existed for a while and neither could create
anything. `tl_form_field` is `tl_module` in miniature: twenty types, a palette
each, and mandatory fields that apply only to some of them.

The command strings are the contract with the bundle, so they are what is
pinned. The per-type requirement rule lives in the bundle and is tested there;
duplicating it here would put the same decision in two places.

⚠️ `form list` and `form fields` still parse Symfony's ASCII table out of
`doctrine:query:sql`, while everything added here answers with JSON from the
bundle. That inconsistency is deliberate for now — migrating the two listings
onto `record:list` changes their output shape and is tracked separately.
"""
from unittest.mock import MagicMock

from click.testing import CliRunner

from contao_ai_cli.contao_cli import cli
from contao_ai_cli.core import form as form_mod


def backend():
    b = MagicMock()
    b.run.return_value = {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""}
    b.run_json.return_value = {"status": "ok"}
    return b


def sent(b) -> str:
    if b.run_json.called:
        return b.run_json.call_args[0][0]
    return b.run.call_args[0][0]


class TestForm:
    def test_read_update_and_delete_use_the_dedicated_commands(self):
        for call, expected in (
            (lambda b: form_mod.form_read(b, 5), "contao:form:read 5"),
            (lambda b: form_mod.form_update(b, 5, {"title": "x"}), "contao:form:update"),
            (lambda b: form_mod.form_delete(b, 5), "contao:form:delete"),
        ):
            b = backend()
            call(b)
            assert expected in sent(b)

    def test_create_passes_the_title(self):
        b = backend()
        form_mod.form_create(b, "Contact")
        cmd = sent(b)
        assert cmd.startswith("contao:form:create")
        assert "--title=Contact" in cmd

    def test_the_alias_is_only_sent_when_given(self):
        """Omitted means "generate it" — sending an empty alias would ask the
        bundle to check a value nobody chose."""
        b = backend()
        form_mod.form_create(b, "Contact")
        assert "--alias" not in sent(b)

        b = backend()
        form_mod.form_create(b, "Contact", alias="contact-us")
        assert "--alias=contact-us" in sent(b)

    def test_email_settings_are_passed_through_as_fields(self):
        b = backend()
        form_mod.form_create(b, "Contact", fields={
            "sendViaEmail": "1", "recipient": "a@b.c", "subject": "New enquiry",
        })
        cmd = sent(b)
        assert "sendViaEmail=1" in cmd
        assert "recipient=a@b.c" in cmd
        assert "'subject=New enquiry'" in cmd


class TestFormField:
    def test_types_uses_the_dedicated_command(self):
        b = backend()
        form_mod.form_field_types(b)
        assert sent(b) == "contao:form-field:types"

    def test_create_sends_the_form_id_and_the_type(self):
        b = backend()
        form_mod.form_field_create(b, 5, "text", {"name": "email", "label": "E-Mail"})
        cmd = sent(b)
        assert cmd.startswith("contao:form-field:create")
        assert "--pid=5" in cmd
        assert "--type=text" in cmd
        assert "name=email" in cmd

    def test_the_options_short_form_reaches_the_server_unsplit(self):
        """The bundle expands it from the DCA. Splitting it here would mean two
        places deciding what an option list is."""
        b = backend()
        form_mod.form_field_create(b, 5, "select", {"options": "mrs=Mrs.|mr=Mr."})
        assert "options=mrs=Mrs.|mr=Mr." in sent(b)

    def test_read_update_and_delete_use_the_dedicated_commands(self):
        for call, expected in (
            (lambda b: form_mod.form_field_read(b, 9), "contao:form-field:read 9"),
            (lambda b: form_mod.form_field_update(b, 9, {"label": "x"}), "contao:form-field:update"),
            (lambda b: form_mod.form_field_delete(b, 9), "contao:form-field:delete"),
        ):
            b = backend()
            call(b)
            assert expected in sent(b)


class TestRegistration:
    def test_every_new_subcommand_is_reachable(self):
        result = CliRunner().invoke(cli, ["form", "--help"])
        assert result.exit_code == 0
        for sub in (
            "read", "create", "update", "delete",
            "field-types", "field-read", "field-create", "field-update", "field-delete",
        ):
            assert sub in result.output, f"form {sub} missing"

    def test_the_existing_listings_keep_their_names(self):
        result = CliRunner().invoke(cli, ["form", "--help"])
        assert "list" in result.output
        assert "fields" in result.output
