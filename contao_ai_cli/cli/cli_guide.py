"""
guide command — print the agent guide (AGENTS.md) of the installed version.

The guide used to live only in the repository. An agent working in a Contao
project, with the CLI installed through pipx, never saw it: the package carried
nothing but the short skills/SKILL.md. Since v0.26.0 the build copies AGENTS.md
into the package (setup.py, build_py), and this command hands it out, so the text
an agent reads matches the version it runs.

Lookup order: the copy inside the package, then the repository root next to it
(an editable install or a plain checkout, where build_py never ran). Read-only;
needs no session.
"""
from pathlib import Path

import click

from .helpers import __version__, _output

_PACKAGE_DIR = Path(__file__).resolve().parent.parent


def guide_path() -> Path | None:
    for candidate in (_PACKAGE_DIR / "AGENTS.md", _PACKAGE_DIR.parent / "AGENTS.md"):
        if candidate.is_file():
            return candidate
    return None


@click.command()
@click.option("--path", "path_only", is_flag=True, help="Print only where the guide is")
@click.pass_context
def guide(ctx, path_only):
    """Print the agent guide (AGENTS.md) for this version."""
    path = guide_path()
    if path is None:
        # Not `self-update`: it does nothing when the version is already current.
        raise click.ClickException(
            "AGENTS.md is not part of this installation. Reinstall with "
            f"python -m pipx install --force git+https://github.com/webwerkwien/contao-ai-cli.git@v{__version__} "
            "or read it at https://github.com/webwerkwien/contao-ai-cli/blob/main/AGENTS.md"
        )

    if ctx.obj.get("as_json"):
        result = {"version": __version__, "path": str(path)}
        if not path_only:
            result["text"] = path.read_text(encoding="utf-8")
        _output(result, True)
        return

    if path_only:
        click.echo(str(path))
        return

    click.echo(path.read_text(encoding="utf-8"), nl=False)
