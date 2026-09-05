"""
The documentation must describe commands that exist.

README.md promised `page … update, delete, publish` and CLAUDE.md gave two literal
examples — `content update --id 5` and `news delete --id 3` — for commands the CLI
did not have, with an option spelling it never used. CLAUDE.md is the agent guide:
it is exactly what a caller reads to decide what to invoke. These tests pin the
docs to the real command tree so the promise cannot drift from the product again.

What these tests do NOT check: what a command answers.

The command tree is the whole question here — name, existence, option spelling.
A changed return value is invisible to them, and exactly that slipped through
twice on 2026-09-01: v0.12.0 changed what `ext run` returns, v0.12.2 added a
`hint` field. Both times this file stayed green and CLAUDE.md — the guide a
calling agent reasons from — said nothing about it.

That is not a weakness of the tests but their boundary. It is written down
because their green is otherwise read as a statement about something they never
looked at, and the file name says "docs match cli" without qualifying which
half. If what a caller sees has changed, no test covers it — that is step 3 of
the release round in the `contao-ai-status` skill.

There is a second half to that boundary, and it is the harder one: these tests
see one repository. The behaviour a sentence in CLAUDE.md describes does not
have to live in the same repository as the sentence.

On 2026-09-05 core-bundle v0.7.0 started refusing non-boolean values for boolean
columns. The paragraph describing the old outcome — "would be stored as 1" —
sits in *this* repository, because that is where the guide for calling agents
lives. Nothing here changed, so nothing here could have gone red. It was found
by a second session reading the release note against the guide.

So the boundary is not only "what a command answers" but also **"where the
promise that changed is written down"**. A cross-repository change needs a human
or an agent holding both, not a test.
"""
import pathlib
import re
import shlex

import click
import pytest

from contao_ai_cli.contao_cli import cli

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
DOCS = [REPO / "README.md", REPO / "CLAUDE.md"]


def command_tree() -> dict:
    """group -> sorted subcommands, plus '' -> standalone commands."""
    ctx = click.Context(cli)
    tree = {"": []}
    for name in sorted(cli.list_commands(ctx)):
        cmd = cli.get_command(ctx, name)
        if isinstance(cmd, click.Group):
            tree[name] = sorted(cmd.list_commands(click.Context(cmd)))
        else:
            tree[""].append(name)
    return tree


def shell_lines(path: pathlib.Path) -> list[str]:
    """Every `contao-ai-cli …` invocation in a fenced block, continuations joined."""
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```(?:bash|shell)?\n(.*?)```", text, re.S)
    lines = []
    for block in blocks:
        joined = re.sub(r"\\\s*(?:#[^\n]*)?\n\s*", " ", block)
        for line in joined.splitlines():
            line = re.sub(r"\s+#.*$", "", line).strip()
            if line.startswith("contao-ai-cli"):
                lines.append(line)
    return lines


def find_option(node, name: str):
    """The parameter `name` belongs to, looking at the node and the root group."""
    for owner in (node, cli):
        for param in owner.params:
            if name in getattr(param, "opts", []):
                return param
    return None


def resolve(tokens: list[str]):
    """
    Walk the click tree to the command an example invokes.

    Options may precede the group — `contao-ai-cli --json page list` — so they are
    skipped along the way, together with their value when they take one.
    """
    node, ctx = cli, click.Context(cli)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            param = find_option(node, token.split("=", 1)[0])
            if param is None:
                break  # unknown option — the option test reports it
            takes_value = not getattr(param, "is_flag", False) and "=" not in token
            i += 2 if takes_value else 1
            continue
        if not isinstance(node, click.Group):
            break
        candidate = node.get_command(ctx, token)
        if candidate is None:
            break
        node, ctx, i = candidate, click.Context(candidate), i + 1
    return node, tokens[i:]


class TestReadmeTable:
    def test_table_matches_the_command_tree(self):
        """The table is generated; a new command has to be regenerated into it."""
        rendered = (REPO / "README.md").read_text(encoding="utf-8")
        for group, subs in command_tree().items():
            if not group:
                continue
            expected = f"| `{group}` | " + " ".join(f"`{s}`" for s in subs) + " |"
            assert expected in rendered, f"README row out of date for `{group}`:\n  {expected}"

    def test_table_lists_no_command_that_does_not_exist(self):
        rendered = (REPO / "README.md").read_text(encoding="utf-8")
        tree = command_tree()
        for row in re.findall(r"^\| `([a-z-]+)` \| (.*?) \|", rendered, re.M):
            group, cell = row
            if group not in tree:
                pytest.fail(f"README lists group `{group}`, which the CLI does not have")
            for sub in re.findall(r"`([a-z-]+)`", cell):
                assert sub in tree[group], f"README lists `{group} {sub}`, which does not exist"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
class TestDocumentedExamples:
    def test_every_example_resolves_to_a_real_command(self, doc):
        failures = []
        for line in shell_lines(doc):
            tokens = shlex.split(line)[1:]
            node, rest = resolve(tokens)
            if isinstance(node, click.Group) and node is not cli:
                continue  # `contao-ai-cli page --help` style, fine
            if node is cli:
                failures.append(f"{line}\n    -> no such command")
        assert not failures, "Documented commands that do not exist:\n  " + "\n  ".join(failures)

    def test_every_example_uses_options_the_command_has(self, doc):
        failures = []
        for line in shell_lines(doc):
            tokens = shlex.split(line)[1:]
            node, rest = resolve(tokens)
            if node is cli:
                continue  # covered by the test above
            known = {o for p in node.params for o in getattr(p, "opts", [])}
            known |= {o for p in cli.params for o in getattr(p, "opts", [])}
            for token in tokens:
                name = token.split("=", 1)[0]
                if name.startswith("--") and name not in known:
                    failures.append(f"{line}\n    -> {name} is not an option of `{node.name}`")
        assert not failures, "Documented options that do not exist:\n  " + "\n  ".join(failures)
