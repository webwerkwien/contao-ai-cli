"""
template group — Manage Contao Twig templates (templates/ directory).
"""
import click

from cli_anything.contao.core import template as template_mod
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def template():
    """Manage Contao Twig templates (templates/ directory)."""
    pass


@template.command("list")
@click.option("--prefix", default="", help="Filter by path prefix, e.g. content_element/")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def template_list_cmd(ctx, prefix, as_json):
    """List custom templates under templates/."""
    _require_bridge(ctx, "template list")
    b = _get_backend(ctx.obj.get("session"))
    _output(template_mod.template_list(b, prefix), as_json or ctx.obj.get("as_json"))


@template.command("read")
@click.option("--path", required=True, help="Template path relative to Contao root, e.g. templates/content_element/text.html.twig")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def template_read_cmd(ctx, path, as_json):
    """Read a template file content."""
    _require_bridge(ctx, "template read")
    b = _get_backend(ctx.obj.get("session"))
    _output(template_mod.template_read(b, path), as_json or ctx.obj.get("as_json"))


@template.command("write")
@click.option("--mode", required=True, type=click.Choice(["override", "partial", "variant"]),
              help="override=replace core template, partial=include-only, variant=selectable in backend")
@click.option("--base", required=True,
              help="Base template path without extension, e.g. content_element/text")
@click.option("--name", default="", help="Variant name (required for mode=variant)")
@click.option("--content", required=True,
              help="Template source as string, or @filename to read from a local file")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def template_write_cmd(ctx, mode, base, name, content, as_json):
    """Write a Twig template. Path is calculated automatically from --mode and --base."""
    _require_bridge(ctx, "template write")
    if content.startswith("@"):
        local = content[1:]
        try:
            with open(local, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            raise click.UsageError(f"Cannot read local file {local!r}: {e}")
    if mode == "variant" and not name:
        raise click.UsageError("--name is required for mode=variant")
    b = _get_backend(ctx.obj.get("session"))
    _output(template_mod.template_write(b, mode, base, content, name),
            as_json or ctx.obj.get("as_json"))
