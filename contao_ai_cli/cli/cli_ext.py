"""
ext group — commands this installation offers that the CLI does not wrap.
"""
import click

from contao_ai_cli.core import ext as ext_mod
from .helpers import _get_backend, _output, _require_core_bundle


@click.group()
def ext():
    """Reach console commands this CLI does not wrap (extensions, plugins, your own).

    Named for what it holds rather than who wrote it: Contao's own unwrapped
    commands land here too, and so does a command from your own site bundle.
    "Third party" would be wrong for both.
    """
    pass


@ext.command("list")
@click.option("--all", "include_infrastructure", is_flag=True,
              help="Also show Contao's own plumbing, with the reason it is normally set aside")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def ext_list_cmd(ctx, include_infrastructure, as_json):
    """What this installation can do that the CLI has no command for.

    The server answers what exists; the subtraction happens here. A command that
    appears in this list is reachable through `ext run`.
    """
    _require_core_bundle(ctx, "ext list")
    b = _get_backend(ctx.obj.get("session"))
    _output(ext_mod.ext_list(b, include_infrastructure), as_json or ctx.obj.get("as_json"))


@ext.command("describe")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def ext_describe_cmd(ctx, name, as_json):
    """Arguments, options and help for one command, read off the server."""
    _require_core_bundle(ctx, "ext describe")
    b = _get_backend(ctx.obj.get("session"))
    _output(ext_mod.ext_describe(b, name), as_json or ctx.obj.get("as_json"))


@ext.command("run", context_settings={"ignore_unknown_options": True})
@click.argument("command_line", nargs=-1, required=True)
@click.option("--operator", default="", help="Acting user identifier for the log entry")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def ext_run_cmd(ctx, command_line, operator, as_json):
    """Run an unwrapped command. Warns, and records that it was started.

    \b
      contao-ai-cli ext run contao:some-plugin:sync --dry-run

    A wrapped command is refused here: the wrapper converts fields, checks them
    against the DCA and shapes the answer, so the bare command would answer
    differently under the same name.
    """
    _require_core_bundle(ctx, "ext run")

    line = " ".join(command_line)

    # Both refusals come before the warning, and the order matters: the warning
    # ends with "the invocation is recorded in the system log". For a command
    # that is refused, nothing is recorded — printing it first said something
    # about the run that had not happened and was not going to.
    if (refusal := ext_mod.refuse_outside_contao(line)) is not None:
        raise click.ClickException(refusal)

    if (refusal := ext_mod.refuse_wrapped(line)) is not None:
        raise click.ClickException(refusal)

    # The warning and the server's log entry are two halves of one decision
    # (2026-09-01), and they have different readers at different times: this
    # reaches the caller before the effect, the log entry reaches whoever asks
    # afterwards what happened. Either alone leaves one of them without an
    # answer.
    b = _get_backend(ctx.obj.get("session"))

    # Asked before the warning is written, because it decides what the warning
    # may say. A command that has declared a trail makes the blanket sentence
    # below untrue, and printing it anyway would be the CLI stating something
    # about the target that the target itself contradicts.
    contract = ext_mod.contract_warning(
        (ext_mod.ext_describe(b, line.split(" ", 1)[0]) or {}).get("contract")
    )

    name = line.split(" ", 1)[0]

    if contract:
        # Not the blanket text plus an appendix. That version said "no promise
        # that it writes a version, an undo entry or a log line" and then listed
        # the trail two lines further down — the warning contradicting itself
        # inside one message.
        click.echo(
            f"Warning: {name} is not wrapped by this CLI, but it declares a contract.\n"
            "The wrapped commands' guarantees still do not apply — no field conversion and\n"
            "no DCA check — and nothing here verifies what follows. The invocation is\n"
            "recorded in the system log before it starts; the outcome is not."
            + contract,
            err=True,
        )
    else:
        click.echo(
            f"Warning: {name} is not wrapped by this CLI.\n"
            "Nothing here knows what it does, so none of the guarantees the wrapped commands\n"
            "carry apply: no field conversion, no DCA check, and no promise that it writes a\n"
            "version, an undo entry or a log line of its own. The invocation is recorded in\n"
            "the system log before it starts; the outcome is not.",
            err=True,
        )
    result = ext_mod.ext_run(b, line, operator)
    _output(result, as_json or ctx.obj.get("as_json"))

    # The envelope reports the foreign command's exit code; the process has to
    # carry it too, or a shell loop around `ext run` reads success from a run
    # that failed. Printed first, so the answer survives the failure — the same
    # reason the server logs before it runs.
    if result.get("exit_code"):
        ctx.exit(1)
