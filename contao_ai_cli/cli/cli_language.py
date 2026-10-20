"""
language group — translation links of terminal42/contao-changelanguage.

Needs core-bundle v1.4.0 and the package installed on the server; without the
package the core does not register these commands.
"""
import click

from contao_ai_cli.core import language as language_mod
from .helpers import _get_backend, _output, _require_core_bundle

_TABLES = [
    "tl_page", "tl_article",
    "tl_news", "tl_news_archive",
    "tl_calendar_events", "tl_calendar",
    "tl_faq", "tl_faq_category",
]


@click.group()
def language():
    """Translation links (terminal42/contao-changelanguage). Needs core-bundle v1.4.0."""
    pass


@language.command("link")
@click.option("--table", required=True, type=click.Choice(_TABLES),
              help="Table of the record in the other language")
@click.option("--id", "record_id", type=int, required=True,
              help="ID of the record in the other language")
@click.option("--main", type=int, required=True,
              help="ID of its counterpart in the main language; 0 removes the link")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def language_link_cmd(ctx, table, record_id, main, as_json):
    """Link a record to its translation in the main language.

    The field follows from the table: languageMain for pages, articles, news,
    events and FAQ, master for their archives, languageRoot for a fallback root —
    linking the main-language root of one domain to that of another domain. A
    root that is not the main language needs no link: it belongs to the fallback
    root of its own domain.
    The target is checked against what the back end offers — an archive is linked
    before its entries, a page before its articles — and written with a version,
    the package's own checks and cache invalidation.
    """
    _require_core_bundle(ctx, "language link")
    b = _get_backend(ctx.obj.get("session"))
    _output(language_mod.language_link(b, table, record_id, main), as_json or ctx.obj.get("as_json"))


@language.command("versions")
@click.option("--table", required=True,
              type=click.Choice(["tl_page", "tl_article", "tl_news", "tl_calendar_events", "tl_faq"]),
              help="Table of the record")
@click.option("--id", "record_id", type=click.IntRange(min=1), required=True, help="ID of the record")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def language_versions_cmd(ctx, table, record_id, as_json):
    """The linked language versions of a record. Reads only. Needs core-bundle v1.11.0.

    Pages, articles, news, events and FAQ: the counterpart in the main language
    and every version linked to it, each with root and language, and the other
    website roots (otherRoots). When none is linked, a note says a version may
    exist there without a link -- "no versions" is not "no other language".
    """
    _require_core_bundle(ctx, "language versions")
    b = _get_backend(ctx.obj.get("session"))
    _output(language_mod.language_versions(b, table, record_id), as_json or ctx.obj.get("as_json"))


@language.command("check")
@click.option("--root", type=int, default=None,
              help="Only this root page (of a language other than the main one)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def language_check_cmd(ctx, root, as_json):
    """Report missing or broken translation links. Reads only.

    Per root of another language: unlinked, invalid and duplicate page links,
    unlinked articles, archives without master and their unlinked entries.
    Articles that cannot be linked -- their page in the main language or its
    root is not published, or outside its start/stop time -- come apart as
    unlinkableArticles, with the reason (core-bundle v1.11.1).
    """
    _require_core_bundle(ctx, "language check")
    b = _get_backend(ctx.obj.get("session"))
    _output(language_mod.language_check(b, root), as_json or ctx.obj.get("as_json"))
