"""user delete and member delete ask first, like every other delete (v0.29.0).

Until v0.28.0 they were the only two of 24 record deletes without a prompt and
without --yes. Both are reversible through tl_undo, so they take the same guard
as page delete: a question on a terminal, none without one, --yes skips it.
"""
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from contao_ai_cli.cli import cli_member, cli_user

CASES = [
    (cli_user, cli_user.user, "user_mod", "user_delete", "admin2"),
    (cli_member, cli_member.member, "member_mod", "member_delete", "anna"),
]


def _run(module, group, mod_name, args, confirmed):
    with patch.object(module, "_require_core_bundle"), \
         patch.object(module, "_get_backend"), \
         patch.object(module, "confirm_delete", return_value=confirmed) as guard, \
         patch.object(module, mod_name) as mod:
        result = CliRunner().invoke(group, args, obj={})
    return result, mod, guard


@pytest.mark.parametrize("module,group,mod_name,func,username", CASES)
def test_declining_deletes_nothing(module, group, mod_name, func, username):
    result, mod, _ = _run(module, group, mod_name, ["delete", username], confirmed=False)
    getattr(mod, func).assert_not_called()
    assert result.exit_code != 0


@pytest.mark.parametrize("module,group,mod_name,func,username", CASES)
def test_confirming_deletes(module, group, mod_name, func, username):
    result, mod, guard = _run(module, group, mod_name, ["delete", username], confirmed=True)
    getattr(mod, func).assert_called_once()
    assert getattr(mod, func).call_args[0][1] == username
    assert username in guard.call_args[0][0]
    assert guard.call_args[0][1] is False


@pytest.mark.parametrize("module,group,mod_name,func,username", CASES)
def test_yes_is_passed_through_to_the_guard(module, group, mod_name, func, username):
    _, mod, guard = _run(module, group, mod_name, ["delete", username, "--yes"], confirmed=True)
    assert guard.call_args[0][1] is True
    getattr(mod, func).assert_called_once()
