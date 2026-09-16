"""
file group — Manage Contao files (DBAFS / tl_files).
"""
import click

from contao_ai_cli.core import session as session_mod, file as file_mod
from .helpers import _get_backend, _output, _require_core_bundle, confirm_escalation


@click.group()
def file():
    """Manage Contao files (DBAFS / tl_files)."""
    pass


@file.command("list")
@click.option("--path", default=None, help="Filter by path prefix (e.g. files/images)")
@click.option("--type", "type_filter", type=click.Choice(["file", "folder"]), default=None,
              help="Show only files or only folders")
@click.option("--limit", type=int, default=None, help="Max rows (1-100, server default 20)")
@click.option("--offset", type=int, default=None, help="Skip this many rows")
@click.pass_context
def file_list_cmd(ctx, path, type_filter, limit, offset):
    """List files and folders from the Contao file manager."""
    _require_core_bundle(ctx, "file list")
    session_path = ctx.obj.get("session") or session_mod.DEFAULT_SESSION_FILE
    b = _get_backend(session_path)
    _output(file_mod.file_list(b, path, type_filter, limit, offset), ctx.obj.get("as_json"))


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
    """Create a folder in the Contao file system via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "file folder-create")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.folder_create(b, path), as_json or ctx.obj.get("as_json"))


@file.command("delete")
@click.option("--path", required=True, help="File or folder below files/, e.g. files/conpai/bild.png")
@click.option("--force", is_flag=True, help="Delete even while the file is still used")
@click.option("--yes", is_flag=True, help="Delete without the prompt — required when no one can answer it")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_delete_cmd(ctx, path, force, yes, as_json):
    """Delete a file or folder with its DBAFS records, as the back end does.

    Refused while the file is still used (image elements, insert tags, paths in
    text) unless --force; the answer lists where. A deleted file cannot be restored,
    so without a terminal it needs --yes — silence at the prompt is a no here.
    """
    _require_core_bundle(ctx, "file delete")
    # Not confirm_delete: that one proceeds when nobody answers, which is right where
    # tl_undo holds the record. Files have no undo, and the review of 2026-09-16 showed
    # how much one wrong path can take — so only --yes or a typed yes deletes.
    if not yes and not confirm_escalation(f"Delete {path}? Files cannot be restored."):
        _output({
            "status": "error",
            "message": f"Nothing was deleted: {path}. Files cannot be restored, so file delete "
                       "needs --yes when no one answers yes at the prompt.",
            "code": 1,
        }, as_json or ctx.obj.get("as_json"))
        ctx.exit(1)
    b = _get_backend(ctx.obj.get("session"))
    result = file_mod.file_delete(b, path, force)
    _output(result, as_json or ctx.obj.get("as_json"))
    # The whole answer is printed — a refusal names its usages — and $? still says
    # that nothing was deleted.
    if isinstance(result, dict) and result.get("status") == "error":
        ctx.exit(1)


@file.command("folder-publish")
@click.option("--path", required=True, help="Folder path relative to Contao root, e.g. files/conpai")
@click.option("--unpublish", is_flag=True, help="Protect the folder again instead of publishing it")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_folder_publish_cmd(ctx, path, unpublish, as_json):
    """Make a folder public (served by the front end), or protect it with --unpublish.

    Does what the back end does: .public, symlinks, log entry. A folder that is
    public through a parent is refused with the reason. Needs core-bundle v0.13.0.
    """
    _require_core_bundle(ctx, "file folder-publish")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.folder_publish(b, path, unpublish), as_json or ctx.obj.get("as_json"))


@file.command("upload")
@click.option("--path",   required=True, help="Destination path relative to Contao root, e.g. files/images/photo.jpg")
@click.option("--source", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Local file to upload — any type the installation's uploadTypes allows")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_upload_cmd(ctx, path, source, as_json):
    """Upload a local file (images, PDFs, fonts, …) to files/.

    Held to the installation's own upload rules: uploadTypes, maxFileSize,
    imageWidth/imageHeight and SVG sanitising. An existing file is versioned
    first. Needs core-bundle v0.13.0.
    """
    _require_core_bundle(ctx, "file upload")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_upload(b, path, source), as_json or ctx.obj.get("as_json"))


@file.command("process")
@click.option("--path", required=True, help="File path relative to Contao root, e.g. files/images/photo.jpg")
@click.option("--allowed-types", default="", help="Comma-separated extensions to narrow Contao's uploadTypes to (cannot widen it)")
@click.option("--max-width",     type=int, default=0, help="Max image width in pixels (0 = use Contao config)")
@click.option("--max-height",    type=int, default=0, help="Max image height in pixels (0 = use Contao config)")
@click.option("--max-file-size", type=int, default=0, help="Max file size in bytes (0 = use Contao config)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_process_cmd(ctx, path, allowed_types, max_width, max_height, max_file_size, as_json):
    """Validate and optionally resize a file already on the server via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "file process")
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_process(b, path, allowed_types, max_width, max_height, max_file_size),
            as_json or ctx.obj.get("as_json"))


@file.command("write")
@click.option("--path",    required=True, help="Destination path relative to Contao root, e.g. files/scripts/style.css")
@click.option("--content", required=True, help="Text content to write (use @filename to read from a local file)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def file_write_cmd(ctx, path, content, as_json):
    """Write text to a file under files/ — an existing file is versioned first.

    Held to uploadTypes and maxFileSize like any upload. For binary files
    (images, PDFs, fonts) use `file upload`.
    """
    _require_core_bundle(ctx, "file write")
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
    _require_core_bundle(ctx, "file read")
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
    """Update metadata fields on a tl_files record via contao-ai-core-bundle."""
    _require_core_bundle(ctx, "file meta")
    invalid = [f for f in fields if "=" not in f]
    if invalid:
        raise click.UsageError(f"Invalid --set value(s): {invalid!r}. Expected format: FIELD=VALUE")
    parsed = dict(f.split("=", 1) for f in fields)
    b = _get_backend(ctx.obj.get("session"))
    _output(file_mod.file_meta_update(b, path, parsed, lang), as_json or ctx.obj.get("as_json"))
