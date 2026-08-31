# contao-ai-cli

Agent-native Python CLI for managing Contao 5 installations from the terminal — over SSH for CRUD, over HTTPS for bulk LLM macros. Designed to be used directly or handed to an AI agent (e.g. Claude Code) as a tool set.

> **Beta software.** CLI command names/options and session JSON format may change between minor versions. Always back up your Contao installation before use.

## The contao-ai ecosystem

| Package | What it is | When to use |
|---|---|---|
| [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) | Contao bundle exposing CMS operations as Symfony console commands. | Required as the foundation layer. Install on any Contao site you want to manage via AI. |
| **contao-ai-cli** *(this package)* | Python CLI — connects to Contao via SSH and runs commands. | For developers and agencies: manage Contao from the terminal or hand control to an AI agent. |
| [contao-ai-backend-bundle](https://github.com/webwerkwien/contao-ai-backend-bundle) | Contao backend module — browser-based AI chat interface (Anthropic Claude, OpenAI). | For editors and admins: AI directly inside the Contao backend, no SSH or terminal needed. |

## What it does

contao-ai-cli works standalone for simple read operations, and unlocks full CRUD support when [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) is installed on the target site. The optional `bridge` group calls macro tools in [contao-ai-backend-bundle](https://github.com/webwerkwien/contao-ai-backend-bundle) over HTTPS for bulk LLM jobs without leaving the terminal.

## Requirements

- Python >= 3.10
- SSH access to your web host
- [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) installed on the Contao site (for full CRUD support)
- [contao-ai-backend-bundle](https://github.com/webwerkwien/contao-ai-backend-bundle) installed on the Contao site (for `bridge` macro calls)

## Installation

The recommended way to install CLI tools on any platform is [pipx](https://pipx.pypa.io) — it ensures the `contao-ai-cli` command is available system-wide without PATH issues.

```bash
# Install pipx if you don't have it yet
pip install pipx
pipx ensurepath

# Install contao-ai-cli
pipx install git+https://github.com/webwerkwien/contao-ai-cli.git
```

## Quick start

```bash
# Connect to a Contao installation and save the session
contao-ai-cli connect --host example.com --user deploy --root /var/www/html --name my-site

# List saved sessions
contao-ai-cli session-list

# Start interactive mode against a session
contao-ai-cli --session my-site repl
```

## Available command groups

Full CRUD needs [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle)
on the target site. This table is generated from the command tree and pinned by a test,
so it cannot drift from what the CLI actually offers.

| Group | Commands | What for |
|---|---|---|
| `article` | `create` `delete` `list` `read` `update` | Articles inside pages |
| `backup` | `create` `list` `restore` | Database backups |
| `bridge` | `clone` `configure` `rewrite` `status` | Bulk LLM jobs via contao-ai-backend-bundle |
| `cache` | `clear` `pool-clear` `pool-list` `warmup` | Symfony cache |
| `comment` | `delete` `list` `publish` | Comment moderation |
| `contao` | `automator` `crawl` `cron` `cron-list` `filesync` `install` `maintenance` `migrate` `resize-images` `setup` `symlinks` | Contao's own maintenance commands |
| `content` | `create` `delete` `list` `read` `update` | Content elements |
| `debug` | `dca` `match` `pages` `plugins` `router` `twig` | Debug utilities |
| `event` | `calendars` `create` `delete` `list` `read` `update` | Calendar events |
| `faq` | `categories` `create` `delete` `list` `read` `update` | FAQ entries and categories |
| `file` | `folder-create` `list` `meta` `process` `read` `sync` `write` | Files in the file system |
| `form` | `fields` `list` | Form definitions |
| `layout` | `read` | Layout configuration |
| `listing` | `data` `modules` | Listing module configuration |
| `mailer` | `test` | Mailer configuration |
| `member` | `create` `delete` `list` `update` | Front end members |
| `messenger` | `consume` `failed` `remove` `retry` `stats` `stop-workers` | Messenger transports |
| `news` | `archives` `create` `delete` `list` `read` `repair-headlines` `update` | News entries and archives |
| `newsletter` | `channels` `list` `subscribers` | Newsletters and subscribers |
| `page` | `create` `delete` `list` `publish` `read` `tree` `update` | Site structure |
| `record` | `list` `schema` | **Any** table with a DCA, incl. extension tables |
| `schema` | `mandatory` `resolve` `show` `sync` | DCA field definitions |
| `search` | `index-create` `index-drop` `reindex` | Fulltext index |
| `security` | `hash-password` | Security helpers |
| `template` | `list` `read` `write` | Twig and PHP templates |
| `user` | `create` `delete` `list` `password` `update` | Back end users |
| `version` | `create` `list` `read` `restore` | Contao's version history |

Record IDs are positional arguments, changed fields are repeated `--set FIELD=VALUE`:

```bash
contao-ai-cli --json page update 12 --set title="Home" --set robots=noindex
```

`delete` cascades to child records and stays recoverable from the back end's *Restore*
module. It asks before deleting when run on a terminal — the same thing the Contao back
end does — and `--yes` skips the prompt for scripts and agents.

### Changing many records at once

`update` also takes a list, applying the same `--set` values to every record in a single
connection:

```bash
contao-ai-cli --json page update --ids=39,40,41 --set max_teiln=4
contao-ai-cli --json page update --ids-from-file tour-pages.txt --set max_teiln=4
```

A file holds one ID per line; `#` starts a comment. **Every record still gets its own
version and its own log entry** — only the connection is shared, and the connection is
what was slow: of the 1.4 s a single record cost, 0.67 s was establishing the SSH
session. The response is a summary (`total`, `succeeded`, `failed`, `ids`, `errors`) and
the exit code is non-zero if any record failed. Needs core-bundle **v0.2.15** or newer.

This is the deterministic path. When the change needs judgement rather than a fixed
value, that is what the bridge below is for — but do not pay a language model to write
a constant.

### Tables without a command of their own

Every other group here covers one entity. `record` covers whatever is left — the server
loads the table's DCA and derives the readable columns, the sortable ones and the
filterable ones from it, so a table belonging to a third-party extension behaves exactly
like a core one:

```bash
contao-ai-cli --json record list tl_image_size
contao-ai-cli --json record list tl_page --filter published=1 --limit 50
contao-ai-cli --json record list tl_content --fields id,type,headline
contao-ai-cli --json record schema tl_image_size
```

A table with no DCA, an unknown column in `--fields`, `--order` or `--filter`: the server
refuses each with a structured error. Nothing is filtered on this side — over SSH the
caller already has full database access, so a client-side allow-list would only be a
second copy of the rules to keep in sync.

Default page size is 20 rows and the server will not go above 100. `record` reads only;
writing stays with the per-entity commands, which carry the DCA's `save_callback`s,
validation and versioning that a generic field-setter would skip.

## Backend bridge — bulk LLM operations without browser

For bulk LLM jobs (translate 50 news entries, clone an entire page tree with all children, rewrite a whole news archive) the SSH+console roundtrip is the wrong tool — every console call is a separate PHP process spawn, the audit trail is split across N `tl_version` rows, and the consuming agent burns time and tokens.

The `bridge` group calls macro tools in [contao-ai-backend-bundle](https://github.com/webwerkwien/contao-ai-backend-bundle) directly over HTTPS, so the entire job runs once on the server with full voter pipeline and atomic audit.

**One-time setup** (the backend bundle must be installed on the target site):

1. In the Contao backend → User profile → AI agent → CLI bridge token → **Generate** → copy the cleartext token (shown once).
2. On the workstation:
   ```bash
   contao-ai-cli --session my-site bridge configure \
       --url https://example.com \
       --token 5.abc123...  --test
   ```

**Usage:**
```bash
# Clone a news archive with all entries (one HTTP call, server-side cascade)
contao-ai-cli --session my-site --json bridge clone \
    --table tl_news_archive --source-id 1 --mod title="Press releases 2026"

# Translate all news in archive 5 (server-side LLM loop, one call)
contao-ai-cli --session my-site --json bridge rewrite \
    --table tl_news_archive --id 5 --recursive \
    --instructions "Translate to English, keep technical terms."
```

`contao-ai-cli health` shows CLI / core-bundle / bridge status without requiring a re-connect.
The bridge line distinguishes three states, because the next step differs:

- **not installed** — contao-ai-backend-bundle is absent from the server.
  Fix with `composer require webwerkwien/contao-ai-backend-bundle`.
- **installed, not configured** — the bundle is there, but this session has no token.
  Fix with `contao-ai-cli bridge configure --url … --token …`.
- **ready** — both.

## Audit trail

Every successful write is recorded on the target site, and the record says the change
came from the CLI rather than from a person in the back end.

- **`tl_log`** — one row per write, visible under *System → System log*, with
  `source = CLI`, the SSH user as `username`, the command name in `func` and the
  returned payload in the text. Purged by Contao's cron after 7 days.
- **`tl_version`** — a restorable snapshot for the ten tables the core bundle covers.
- **`tl_undo`** — deletions, including everything that cascaded with them.

Needs contao-ai-core-bundle v0.2.13 or newer on the target site; `contao-ai-cli health`
reports the installed version.

**The trail exists because writes go through this CLI — not because the server keeps
one.** The same SSH connection this tool needs also reaches `mysql`, and a row changed
that way has no version, no undo entry and no log line. Nothing fails; the change just
has no history, and serialised columns (a headline is stored as a PHP-serialised
`{value, unit}` pair) quietly break when a `REPLACE()` edits the text without the byte
count. Reading with `SELECT`, `SHOW` or `mysqldump` is unaffected and perfectly fine.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for what changed in each release.

## License

MIT — see [LICENSE](LICENSE).

This software is provided "as is", without warranty of any kind. The authors accept no liability for any damages arising from its use. Always back up your data before use.
