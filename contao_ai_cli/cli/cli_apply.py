"""`apply --file`: many page, article and content writes, all or nothing (v1.16.0)."""
import json
import sys

import click

from contao_ai_cli.core import apply as apply_mod
from .helpers import _get_backend, _output, confirm_action, json_option


@click.command("apply")
@click.option("--file", "path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="JSON plan: {\"steps\": [...]}, see `guide`")
@click.option("--dry-run", is_flag=True, help="Run every step on the server, then roll back")
@click.option("--yes", "-y", "assume_yes", is_flag=True, help="Do not ask about deletions in the plan")
@click.pass_context
@json_option
def apply(ctx, path, dry_run, assume_yes):
    """Run page, article and content writes from one file, all or nothing.

    Needs core-bundle v1.13.0. The server checks the whole plan before the
    first write; a failing step rolls back every step before it.
    """
    with open(path, encoding="utf-8-sig") as f:   # -sig: a BOM from PowerShell is not part of the plan
        text = f.read()
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        raise click.UsageError(f"{path} is not valid JSON: {exc}")
    steps = plan.get("steps") if isinstance(plan, dict) else None
    count = len(steps) if isinstance(steps, list) else 0
    deletions = sum(1 for s in steps or [] if isinstance(s, dict) and str(s.get("do", "")).endswith(" delete"))
    if deletions and not dry_run and not confirm_action(f"Run a plan with {deletions} deletion(s)?", assume_yes):
        raise click.Abort()

    ctx.ensure_object(dict)
    as_json = ctx.obj.get("as_json")
    try:
        answer = apply_mod.run_apply(_get_backend(ctx.obj.get("session")), text, dry_run, count)
    except apply_mod.ApplyFailed as exc:
        if as_json:
            # The server's own answer, not the generic error object: it carries
            # failedStep and problems, which is what a caller needs to fix the plan.
            click.echo(json.dumps(exc.payload, indent=2, ensure_ascii=False))
            sys.exit(1)
        raise click.ClickException(_describe_failure(exc.payload))
    if as_json:
        _output(answer, True)
        return
    for step in answer.get("steps", []):
        click.echo(f"{step.get('index', ''):>3}  {step.get('do', ''):<15} {step.get('ref', ''):<12} {step.get('id', '')}")
    click.echo(f"{answer.get('count', 0)} step(s) "
               + ("checked and rolled back (dry run; IDs are provisional)" if answer.get("dryRun") else "written"))


def _describe_failure(payload: dict) -> str:
    problems = payload.get("problems") or []
    if problems:
        return payload.get("message", "") + "\n  " + "\n  ".join(str(p) for p in problems)
    return payload.get("message", "apply failed")
