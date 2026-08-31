"""Table-agnostic record access (contao:record:list).

The one read path that is not tied to a fixed entity. The server derives the
allowed columns from `$GLOBALS['TL_DCA']` after `Controller::loadDataContainer()`,
so any table with a DCA works — including tables that belong to a third-party
extension, which no dedicated command in this CLI covers.

The command has existed in the core bundle since the very first releases, but
its only caller was `RecordListTool` in contao-ai-backend-bundle: it was built
for the browser chat, and this CLI never reached for it. There it is gated to
ten hard-coded tables, because a backend user's reach has to follow their
module permissions. Over SSH that gate buys nothing — whoever can run this
already has full access — so nothing is filtered here.

Deliberately no client-side validation of table names, filters or limits: the
server validates all three against the live DCA and answers with a structured
error. A second copy of those rules here would be a second thing to keep in
sync, and this project has already paid for that once (see the TABLE_MODULE
comment in the backend bundle).
"""
import shlex

from contao_ai_cli.utils.contao_backend import ContaoBackend


def record_list(
    backend: ContaoBackend,
    table: str,
    limit: int | None = None,
    offset: int | None = None,
    order: str | None = None,
    filters: tuple[str, ...] = (),
    fields: str | None = None,
) -> dict:
    """List records from any Contao table that has a DCA.

    `filters` are raw "field=value" strings, repeatable, as the server expects
    them. Server-side defaults apply when an argument is omitted (limit 20,
    max 100, order `id DESC`) — they are not duplicated here.
    """
    cmd = f"contao:record:list {shlex.quote(table)}"

    if limit is not None:
        cmd += f" --limit {int(limit)}"
    if offset is not None:
        cmd += f" --offset {int(offset)}"
    if order:
        cmd += f" --order {shlex.quote(order)}"
    if fields:
        cmd += f" --fields {shlex.quote(fields)}"
    for f in filters:
        cmd += f" --filter {shlex.quote(f)}"

    return backend.run_json(cmd)


def dca_schema(backend: ContaoBackend, table: str) -> dict:
    """Field definitions for TABLE, straight from the live DCA as JSON.

    Distinct from the `schema` group, which parses `debug:dca` text output into
    a local cache file. This is the core bundle's own `contao:dca:schema`: no
    cache, no parsing, whatever the server currently declares.
    """
    return backend.run_json(f"contao:dca:schema {shlex.quote(table)}")
