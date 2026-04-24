"""
file group — Manage Contao files (DBAFS / tl_files).
"""
import click

from cli_anything.contao.core import session as session_mod, file as file_mod
from .helpers import _get_backend, _output, _require_bridge


@click.group()
def file():
    """Manage Contao files (DBAFS / tl_files)."""
    pass


@file.command("list")
@click.option("--path", default=None, help="Filter by path prefix (e.g. files/images)")
@click.option("--type", "type_filter", type=click.Choice(["file", "folder"]), default=None,
              help="Show only files or only folders")
@click.pass_context
def file_list_cmd(ctx, path, type_filter):
    """List files and folders from the Contao file manager."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(file_mod.file_list(b, path, type_filter), ctx.obj.get("as_json"))


@file.command("sync")
@click.pass_context
def file_sync_cmd(ctx):
    """Synchronize the DBAFS with the virtual filesystem (contao:filesync)."""
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(file_mod.file_sync(b), ctx.obj.get("as_json"))


@file.command("folder-create")
@click.option("--path", required=True, help="Folder path relative to Contao root, e.g. files/images/gallery")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_folder_create_cmd(ctx, path, as_json):
    """Create a folder in the Contao file system via contao-cli-bridge."""
    _require_bridge(ctx, "file folder-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.folder_create(b, path), as_json or ctx.obj.get("as_json"))


@file.command("process")
@click.option("--path", required=True, help="File path relative to Contao root, e.g. files/images/photo.jpg")
@click.option("--allowed-types", default="", help="Comma-separated allowed extensions (overrides Contao config)")
@click.option("--max-width",     type=int, default=0, help="Max image width in pixels (0 = use Contao config)")
@click.option("--max-height",    type=int, default=0, help="Max image height in pixels (0 = use Contao config)")
@click.option("--max-file-size", type=int, default=0, help="Max file size in bytes (0 = use Contao config)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_process_cmd(ctx, path, allowed_types, max_width, max_height, max_file_size, as_json):
    """Validate and optionally resize a file already on the server via contao-cli-bridge."""
    _require_bridge(ctx, "file process")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_process(b, path, allowed_types, max_width, max_height, max_file_size),
            as_json or ctx.obj.get("as_json"))


@file.command("write")
@click.option("--path",    required=True, help="Destination path relative to Contao root, e.g. files/scripts/style.css")
@click.option("--content", required=True, help="Text content to write (use @filename to read from a local file)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_write_cmd(ctx, path, content, as_json):
    """Write a text file to files/ on the server and create a version snapshot."""
    _require_bridge(ctx, "file write")
    if content.startswith("@"):
        local = content[1:]
        try:
            with open(local, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            raise click.UsageError(f"Cannot read local file {local!r}: {e}")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_write(b, path, content), as_json or ctx.obj.get("as_json"))


@file.command("read")
@click.option("--path", required=True, help="File path relative to Contao root, e.g. files/scripts/style.css")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_read_cmd(ctx, path, as_json):
    """Read a text file from files/ on the server (UTF-8, max 512 KB)."""
    _require_bridge(ctx, "file read")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_read(b, path), as_json or ctx.obj.get("as_json"))


@file.command("meta")
@click.option("--path", required=True, help="File or folder path relative to Contao root")
@click.option("--lang", default="en", show_default=True, help="Language key matching the Contao root-page language")
@click.option("--set", "fields", multiple=True, metavar="FIELD=VALUE",
              help="Metadata field to update, e.g. --set alt=Landscape --set title=Mountain View")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_meta_cmd(ctx, path, lang, fields, as_json):
    """Update metadata fields on a tl_files record via contao-cli-bridge."""
    _require_bridge(ctx, "file meta")
    invalid = [f for f in fields if "=" not in f]
    if invalid:
        raise click.UsageError(f"Invalid --set value(s): {invalid!r}. Expected format: FIELD=VALUE")
    parsed = dict(f.split("=", 1) for f in fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_meta_update(b, path, parsed, lang), as_json or ctx.obj.get("as_json"))
