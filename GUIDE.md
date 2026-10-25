# contao-ai-cli — Agent Guide

This is an agent-native CLI for managing Contao 5 installations via SSH.
It wraps Contao's Symfony Console (`php bin/console`) and provides structured
output suitable for AI-driven workflows.

This guide is for any agent that uses the CLI against a Contao site, whatever the tool.
It ships with the installed package, so an agent working in a Contao project reads the
text for the version it is running:

```bash
contao-ai-cli guide          # the whole guide, as Markdown
contao-ai-cli guide --path   # only where the file is
```

With `--json`: `{"version", "path", "text"}`; `--path` leaves out `text`. Exit 1 with a
message naming the reinstall command if the installation carries no guide.

---

## Step 1: Check for existing sessions

```bash
contao-ai-cli session-list
```

If a session exists, you can start using commands immediately — **with
`--session <name>` on every command**, using a name from that list. Without `--session`
the CLI uses the session named `session` (what `connect` saves when no `--name` is
given), not the only or the first one; if there is none, the command fails with
`No session named 'session'` and lists the known ones (a few commands that need no core
bundle, such as `cache`, answer `Session file not found` instead).
Session files are stored in `~/.contao-ai-cli/<name>.json`.

## Step 2: Connect (first time only)

```bash
contao-ai-cli connect \
  --host your-server.example.com \   # hostname or IP of your web server
  --user ssh-username \              # SSH login user
  --root /path/to/contao \          # absolute path to the Contao root on the server
  --key ~/.ssh/id_ed25519 \         # path to your SSH private key (adjust if different)
  --name my-site \                  # local session name (your choice)
  --json
```

**Since v0.21.0 `connect` does not ask anything.** It tests the connection first
(`--version`) and saves the session only on success — on failure it exits 1 with a
message and nothing is written. Everything that used to be a prompt is now in the
`--json` answer: a `warning` to relay verbatim, the same `state` block `health` reports,
and an ordered `nextSteps` list (backup, bundle install/update, self-update, bridge
configure) for you to confirm with the user one at a time. Full field-by-field
description below, under "Setup and updates (v0.21.0)".

This also means `connect` is no longer a step that needs a human at a terminal — an
agent runs it directly, once it has host, user and root path from the person.

**From Git Bash on Windows, set `MSYS_NO_PATHCONV=1`.** MSYS rewrites an argument that
starts with `/` into a Windows path: `--root /var/www/web` reaches the CLI as
`C:/Program Files/Git/var/www/web`, and the server answers `cd: … No such file or
directory`. Since v0.27.0 the error message says so when the root carries the Git prefix;
since v1.7.0 for any folder behind it (`/web`, `/html`, `/htdocs`, `…/public_html`),
recognised by the usual Git install locations and the Git installation on this machine.

> ⚠️ Never hardcode real hostnames, usernames, passwords, or key paths
> in any committed file. Always ask the user for connection details.

## Setup and updates (v0.21.0)

Everything a calling agent needs to drive setup end to end, and to keep a site current
afterwards, without a wizard. `README.md` has the step-by-step guide ("Set up with an
agent"); this is the shape of what each command answers.

### `connect`'s answer

```json
{
  "status": "connected",
  "session": "/home/user/.contao-ai-cli/my-site.json",
  "replaced": false,
  "version": "Contao 5.7.0",
  "warning": "contao-ai-cli can change or delete data on this site irreversibly. Make sure a current backup exists before anything is written.",
  "state": { "cli": {}, "contao": {}, "core": {}, "backend": {}, "bridge": {} },
  "nextSteps": [
    { "command": "contao-ai-cli --session my-site backup create", "optional": false, "reason": "A database backup before anything is written." },
    { "command": "contao-ai-cli --session my-site bundle install core", "optional": false, "reason": "contao-ai-core-bundle is missing; without it only Contao's own console commands work." }
  ]
}
```

- **Relay `warning` to the user, word for word**, before doing anything else.
- **Go through `nextSteps` in order and confirm each one in chat before running it.**
  An entry with `optional: true` (`bundle install backend` for bulk jobs, `bridge
  configure` for `bridge clone`/`rewrite`, and in `health` a backup before an optional
  install) is offered, not assumed — skip it unless the user wants it.
- `host_key_accepted` is present only on a first contact with the host — information, not
  a failure, and it appears only that once. **Relay it to the user**; if they did not
  expect a first contact with this host, they should verify the fingerprint with the
  server themselves before trusting it further (trust-on-first-use).
- `replaced: true` means an existing session file at that name was overwritten.
  **Reconnecting keeps `bridge_url`/`bridge_token` from the existing session** — only the
  SSH fields are replaced. Fixed in v0.21.0: up to v0.20.0 a re-`connect` silently
  dropped a configured bridge, because saving a session used to rewrite the whole file.
- Exit code `0` and the object above on success; exit code `1` and
  `{"status": "error", "code": 1, "message": "..."}` on a failed connection test, with
  nothing saved.

### `bundle install|update core|backend [--allow-plugins]`

Moved out of the old wizard, so these two operations — installing or
updating either contao-ai bundle — are reachable at any time, not only during setup:

```bash
contao-ai-cli --session my-site bundle install core
contao-ai-cli --session my-site bundle install backend  # refused: missingAllowPlugins
contao-ai-cli --session my-site bundle install backend --allow-plugins  # only after the user agreed to write composer.json
contao-ai-cli --session my-site bundle update core
```

On a **Managed Edition** it goes through the Contao Manager's Composer passthrough
(`php public/contao-manager.phar.php composer …`), which uses the manager's own
`allow-plugins` config — the project `composer.json` is left untouched. Without a
Contao Manager, plain `composer` is used, and a missing `allow-plugins` entry is
**refused**: the answer names the missing plugins in `missingAllowPlugins` and points
at `--allow-plugins`. Writing `allow-plugins` into the project's `composer.json` is
consent the agent asks the user for before passing that flag.

**`install` and `update` both run `composer require "<pkg>:<range>"`, not `composer update`**
— a `composer update` never leaves the constraint already on disk. The range is the one each
bundle's README recommends: core `^1.0`, backend `>=0.1 <2.0` (v1.0.0; see below).

**The bundle brings its own dependencies along** (v1.3.0): the `require` carries
`--update-with-dependencies --minimal-changes`. Without it Composer may change only the
bundle itself, so a release that raises one of its dependencies resolved to the installed
version — backend v0.11.0 needs `symfony/ai ^0.14`, and on a lock holding 0.13 `bundle update
backend` stayed on v0.10.0. `-w`, not `-W`: root requirements — Contao itself —
stay where they are, so a bundle update never lifts Contao on the side. `--minimal-changes`
moves only what has to move; measured on a copy of that lock, it upgraded exactly the backend
and the nine `symfony/ai` packages, where `-w` alone took seven more (Contao components,
`doctrine/orm`). A Composer older than 2.7 does not know `--minimal-changes`; the CLI then
repeats the run with `-w` alone, recognised by Composer's own "option does not exist" — never
after a real resolution failure. What moved besides the bundle is in `dependenciesChanged`.

**Then the database: `contao:migrate` runs after Composer** (v1.7.0), and `migrate` in the
answer says what it did — `{"migrations": 1, "schemaChanges": 5, "backup": "backup__….sql.gz"}`.
Up to v1.6.0 `bundle install backend` answered ok while the bundle's `tl_user` columns were
still missing. Contao dumps the database before it migrates (`backup`, `null`
when there was nothing to do), and without interaction it leaves out `DROP` statements:
columns and tables are added, nothing is deleted. A failed migration — Contao's `error`
with exit 1, a schema change that still fails after Contao's retries (its `schema-result`
carries the reason), or a migration reported unsuccessful with exit 0 — is
`"status": "error"` with
`installed` still set: the package is in place, the database is not; fix the cause and run
`contao-ai-cli contao migrate`. Contao's warnings (non-strict SQL mode, row size) are in
`migrate.warnings`. A run that installs nothing (already installed, already newest)
migrates nothing either.

If an update needs a newer **Contao** (the bundle requires it, or Composer blocks the locked
Contao version for a security advisory, as `enshrined/svg-sanitize` 0.22 was blocked
once), Composer refuses and `stderr` says why. Update Contao first — through the Contao
Manager, or its passthrough with `"contao/*" --with-dependencies` — then the bundle.

The answer is `status: error` unless the version read back afterwards equals `latest` exactly;
if something else holds the newest back (a PHP requirement, a locked dependency), Composer
still exits 0 with an older version — the error then names the installed and the newest
version and says that `composer.json` and the lock were rewritten. If Packagist cannot be reached,
`update` answers `status: error` too (never "up to date" for a version it could not
check). `install_bundle` also probes the server first (`--version`) and answers `status:
error, message: "server not reachable: …"` before touching Composer or allow-plugins at
all — a probe failure used to fall through and be misreported as a missing
`allow-plugins` entry.

| key | present | meaning |
|---|---|---|
| `status` | always | `ok` or `error` |
| `changed` | on success | whether the installed version actually changed |
| `installed` | on success, and on an update whose read-back version is not the newest | version read back after the operation, or the already-installed/up-to-date version |
| `previous` / `via` | **only when Composer actually ran** — absent for "already installed" and "already up to date" answers | version before the run / `contao-manager` or `composer` |
| `missingAllowPlugins` | on refusal | the plugins composer.json does not allow yet |
| `allowPluginsWritten` | when `--allow-plugins` wrote something | the plugins it wrote |
| `constraint` | on success, and on an update held back below the newest | the constraint now in the project's `composer.json`: core `^1.0`, backend `>=0.1 <2.0` |
| `dependenciesChanged` | **only when Composer ran without error** (v1.3.0) — on success, on an update held back below the newest, and when the bundle is missing afterwards | every other package that moved: `{name: {"from": old, "to": new}}`, `null` on either side for one added or removed. `{}` = nothing else moved; `null` = the installed packages could not be read, so it is unknown — never "nothing" |
| `stderr` | when Composer (or the cache warmup) failed and said something (v1.1.1) | the server's **whole** stderr, without PHP's start-up warnings. `message` holds an excerpt |
| `migrate` | **only when Composer ran** (v1.7.0) | what `contao:migrate` did: `migrations`, `schemaChanges`, `backup` (Contao's dump, `null` when nothing to do), `warnings`, `error` |
| `nextSteps` | after `bundle install\|update backend` with the bundle installed, while the session has no bridge (v1.8.0) | the optional `bridge configure` step, same shape as in `connect` |

**Read `stderr`, not only `message`, when Composer refuses.** `message` carries an excerpt,
and an excerpt has to guess what matters. For a Composer problem report it keeps the whole
`Problem N` block minus the lines that explain nothing (`-> satisfiable by …`, progress), and
cuts the middle only past 4000 characters. Until v1.1.1 it kept the last 1500 characters, and
on a Contao 5.3 installation that dropped both real reasons — `symfony/clock` and
`contao/core-bundle` held by the lock file — while keeping lines about long-gone releases that
named the core constraint, the wrong cause. Which line of a problem block is *the* reason,
Composer does not say: the ones with a `but` (`fixed to … (lock file version)`, `conflicts
with`) are the candidates.

**Both commands write that constraint into `composer.json`** (v0.21.2) — the form each
bundle's README recommends, so later updates through the Contao Manager or `composer update`
reach every following minor. A differing constraint is replaced by it, even a deliberately
stricter one. The core bundle is 1.x since 1.0.0: a site still on `>=0.2 <1.0` gets `^1.0`
on its next `bundle update core` (v1.0.0 of this CLI; before it wrote `>=0.2 <1.0`, which
never reaches 1.0). The backend bundle is still 0.x; its range crosses 0.x minors and a
later 1.x. **Update the backend bundle first** where it is installed: up to its v0.9.1 it
requires core `<1.0`, and Composer refuses core 1.0 next to it. Up to v0.21.1 `bundle
update core` wrote `^<latest>` (on a live installation it turned `>=0.2 <1.0` into `^0.20.0`) and
`bundle install core` Composer's own `^0.x` — both capped the next minor.

Success is reported only once the new version has been **read back** from the server —
a Composer run finishing without error is not, on its own, taken as proof.

### Installing an extension this CLI does not manage

`bundle install` takes `core` and `backend` and refuses anything else, with a message
saying what to do instead. That is a boundary, not a gap: `install_bundle` knows our two
packages' version constraints and reads the installed version back, and it knows neither
for a foreign package.

> 🎯 **Installing packages is outside this CLI — and that is the one place where "do not
> go around this CLI" (see "None of it happens if you go around this CLI") does not
> apply.** It is written down because the absence of a route used to read as "so it must
> somehow go through here". It does not.

Ask for the command rather than assuming one; a Managed Edition and a plain Composer
install need different ones, and using the wrong one on a Managed Edition writes into
`composer.json` behind the manager's back:

```bash
contao-ai-cli --session my-site health --json
# -> "composer": {"via": "contao-manager", "command": "/usr/bin/php8.3 public/contao-manager.phar.php composer"}
```

Then run that command over the same SSH connection, from the Contao root — **dry run
first**, and ask the user before the real one: it changes what is installed on their site.

```
<composer.command> require terminal42/contao-changelanguage --dry-run
<composer.command> require terminal42/contao-changelanguage
```

The dry run says *"./composer.json has been updated"* — and leaves nothing behind: in a dry
run Composer does not write the file, whatever the message says. No need to check or
restore it. If you copy
`composer.json` aside anyway, remove the copy afterwards; the operator did not ask for files
left on the server.

Three things afterwards:

- **`via: "composer"`** (no Contao Manager) means the project's own `allow-plugins` has to
  permit Contao's plugins, or Composer refuses. The same consent question as
  `bundle install --allow-plugins`, and it is the user's to answer.
- **If the extension adds database columns**, run `contao migrate` (`--dry-run` first).
  Composer installs the code; the columns exist only after the migration, and a write to
  one of them fails until then. The dry run shows what is pending *now*. The real call runs
  a second round of migrations after the schema update, so a migration that only becomes
  due through the new columns runs without having been listed (seen with
  `Version507\PrepareForOutputEncodingMigration`). Have a backup first, as always.
- **If the extension adds DCA fields**, the cached schema is stale and `schema show` now
  describes a table that no longer looks like that: `schema sync <table>`. An extension
  that extends `tl_member` or `tl_page` is the normal case, not the exception.

**Reading an extension's own tables.** `record list` and `record schema` take any table
with a DCA, also one without `tl_` (core-bundle v1.9.2; up to v1.9.1 such a name was an
"Invalid table name"). What they cannot give you is a DCA the extension does not build on
the console. Some build it only in a web request — the Catalog Manager is the known case:
`alnv/catalog-manager-bundle` (v4) answers `DCA not found` for a catalog,
`alnv/catalog-manager` (v2) shows only the catalog's own fields, without `title`, `alias`
and the visibility fields. That is the extension's behaviour, not a missing table; say so
to the operator rather than reading the table some other way. Writing to such a table
needs a command of the extension's own (see `ext` and `#[AiContract]`); this CLI has no
generic write for foreign tables.

> ⚠️ **`alnv/catalog-manager` v2.0.26 breaks `contao migrate` and the cache warmup on
> Doctrine DBAL 4** as soon as a catalog has fields: its schema listener passes
> `scale: null`, and DBAL 4 refuses it with a `TypeError` the listener does not catch. The
> back-end module of the catalog stops working too. v4 (`catalog-manager-bundle`) does not
> have this. Seen on Contao 5.7.15 with DBAL 4.4.5.

### `self-update`

Reinstalls contao-ai-cli itself at the newest tag via pipx:

```bash
contao-ai-cli self-update --json
```

Answers `{"status": "ok", "changed": true, "previous": "0.20.0", "installed": "0.21.0", "message": "..."}`,
or `changed: false` with `message` saying it is already up to date. Fails naming how to
install pipx if it is missing. A running `repl` keeps the old code in memory until it is
restarted.

### The update notice — one line, on stderr, never in a JSON answer

```
Updates: CLI 0.20.0 -> 0.21.0, core-bundle v0.18.0 -> v0.19.0 - contao-ai-cli health
```

Printed on the first command of a session after a pause of more than 12 hours, and at
least every 24 hours regardless, so continuous use (cron, monitoring) still gets
checked eventually. Skipped for `health`, `self-update`, `bundle`, `connect`, `repl`,
`session-list`, `session-delete`, `guide` (purely local — nothing remote to check) and any
`--help` — they report or do not need version information themselves. Also skipped
when the command itself failed: a failing command has nothing to say
about whether the CLI or the bundles are current. Off entirely with
`CONTAO_AI_CLI_NO_UPDATE_CHECK=1` (CI, cron).

**When this line appears: tell the user and ask whether to update — do not update on
your own.** stdout and every JSON contract are unaffected; nothing about parsing
output changes because of this line.

### Bridge token — the user chooses

- **Hidden prompt.** `bridge configure --url https://…` with neither `--token` nor
  `--token-stdin`, run on a terminal, asks for the token with hidden input. It never
  reaches the chat.
- **Through you.** The user pastes the token in chat and you pipe it in:
  `bridge configure --url https://… --token-stdin --test`. No terminal step for the
  user, but the token then sits in the conversation history.
- `--token` on the command line still works and is documented as visible in the
  process list on both ends of the connection — prefer one of the two above when
  either is possible.

**The bridge is optional — say so** (v1.8.0). Only `bridge clone` and `bridge rewrite` use
it; the back-end chat and every other command of this CLI work without a token. Generating
the token in the back end is only the first half; the second is `bridge configure`. Until
then `bridge.state` is `not_configured`, which is not a fault. `connect`, `health --json`
and a successful `bundle install|update backend` (while the session has no bridge) name it
as an optional next step. Offer it, do not push it.

### `health --json` has `nextSteps` (new in v1.8.0)

The same list `connect` answers with, in the same shape. A `backup create` leads it only
when a `bundle …` step follows; on a site that is up to date the list can be empty or hold
only optional steps.

### `health --json` has a `backend` key (new in v0.21.0)

The backend-bundle counterpart of `core`: `installed`, `latest`, `update_available`.
`bridge.state` (`not_installed` / `not_configured` / `ready`) still says what to do
about the bridge itself; `backend` is about whether contao-ai-backend-bundle is on the
server at all and current, independent of whether this session has a token for it.

### `health --json` has a `composer` key (new in v1.1.0)

How Composer is reached on *this* site, and the exact command to reach it with. It is not
an update line; it exists so nothing has to be guessed when a package has to be installed.
See "Installing an extension this CLI does not manage" below.

| key | meaning |
|---|---|
| `via` | `contao-manager` or `composer`. **`null` means the server could not be looked at**, never "there is no Composer" |
| `command` | the exact command — the same string `bundle install` runs, so the documented and the executed one cannot drift |
| `managerPhar` | path to the manager phar, or `null` |
| `managerBundle` | whether `contao/manager-bundle` is in `composer.lock` |
| `note` | present only when the two signals need explaining — read it before acting |

> ⚠️ **`via: "composer"` has two quite different causes, and only `note` tells them apart**
> (issue #59). A Managed Edition with no manager installed — plain Composer is then the
> right route. Or a manager phar whose config directory is missing, where plain Composer
> writes into `composer.json` past the manager. Unlike `bundle install`, which is caught a
> step later by its allow-plugins check, this advice has nothing behind it.

## Step 3: Use JSON output for machine-readable results

Always use `--json` when processing output programmatically:

```bash
contao-ai-cli --json page list
contao-ai-cli --json news list
contao-ai-cli --json user list
contao-ai-cli --json backup list
```

`--json` works before the command or after it: `contao-ai-cli news list --json` is the
same call (every command since v1.15.0; `repl` is interactive and has no JSON form).
Errors come back as `{"status": "error", "code": N, "message": "..."}` on stdout.

A command name that does not exist answers with exit 2 and, where one fits, a
suggestion in the message: `content get` → `No such command 'get'. Did you mean
'content read'?` The CLI has one name per command and no aliases; `read`, `create`,
`update`, `delete` and `list` are the names to use.

### One thing the output does not tell you literally

**A `tinyint` column comes back as `true`/`false`, never as a number.** Doctrine
maps every MySQL `tinyint` to boolean regardless of its declared width, and Contao
casts accordingly when a record is read through the model layer. A page storing
`stunden = 2` therefore answers:

```json
{ "stunden": true }
```

The database still holds the `2` — only this reading of it is lossy. For flags
(`published`, `hide`, `protected`) that is exactly right and nothing to worry about.
It bites where a project has declared a *number* as `tinyint`.

Two rules follow:

- **Never write a value back that you read from such a field.** `2` returns as
  `true`, and what happens when you send that back depends on how the column is
  declared:

  | the column's DCA `sql` | `--set feld=true` | who declares it that way |
  |---|---|---|
  | `['type' => 'boolean']` | **refused** — `{"status":"error"}`, exit 1, nothing written | every flag in Contao's own DCA (`published`, `hide`, `protected`) |
  | `'tinyint(4) NOT NULL …'` | stored as `1` — the value is lost silently | a project that declared a *number* as tinyint |

  The refusal arrived with core-bundle **v0.7.0**: Contao 6 casts any text into
  the column's type instead of letting the database refuse it, so
  `--set published=vielleicht` used to publish the page and report success.
  Boolean columns now take `1`, `0` or an empty value only — `true`, `yes` and
  `on` are refused too.

  ⚠️ **The second row is the one to keep in mind.** It is not covered and cannot
  be: the column is declared as a number, so refusing a number would break the
  field. That is exactly the `stunden` case below, and it still fails silently.

  Setting a field outright is safe — `--set stunden=2` passes a string and never
  meets the cast.
- **When you need the stored number, query it.** Reading SQL directly is fine:
  `SELECT id, stunden FROM tl_page WHERE id = 98`.

If you are adding fields to a Contao project, declare numbers as
`smallint(5) unsigned`, which is what Contao's own DCA does; it keeps `tinyint`
for flags only.

## Common workflows

### Content management

```bash
# Read — record IDs are positional arguments, not --id
contao-ai-cli --json page list
contao-ai-cli --json page read 1
contao-ai-cli --json article list --page 1
contao-ai-cli --json content list --article 1   # direct elements only (v0.28.0)

# Find — the element that shows a text, with article, page, root and language
# (v1.12.0, core-bundle v1.10.0); an element of a news entry or event names that
# entry under `parent` instead. `more: true` means there are more than --limit
# (default 20, at most 50). Not `search`: the search index answers pages, and a page
# with noindex (staging, a showcase) is never in it.
contao-ai-cli --json content find "A powerful CMS"
contao-ai-cli --json content find "Über uns" --root 1   # one website or language
contao-ai-cli --json content find "digital" --limit 50 --offset 50   # the next page while more: true (core v1.12.0)
# With changelanguage each hit names the linked versions of its page and article in the
# other languages (`versions`, core v1.11.0); see "Translation links" below.

# Create — --pid of a top-level page is the root of its domain; a root with an
# empty dns answers every domain (see "Page URLs, second languages, cloning").
# Only a root may stand at the top level: without --pid, use --type root (core v1.2.0)
contao-ai-cli --json page create --title "New Page" --pid 1 --type regular
# A regular page comes with its first article (`articles` in the answer) — put content
# there. article create only for a further article, e.g. another layout column:
contao-ai-cli --json article create --title "Sidebar" --pid 12 --column right
# Between two existing ones: --after <sibling ID> instead of --pid — the new record goes
# directly behind it, below the same parent (and for an element its parent table), as
# `move --after` places it. Do not compute --set sorting yourself (core v1.12.0).
contao-ai-cli --json content create --type text --after 640 --text '<p>In between</p>'
contao-ai-cli --json article create --title "Second" --after 12
contao-ai-cli --json page create --title "Between A and C" --after 21

# Content elements — the value formats, as schema does not show them
contao-ai-cli --json content create --type headline --pid 7 --set headline="Title" --set headline_unit=h1
contao-ai-cli --json content create --type text --pid 7 --text '<p>See <a href="https://contao.org">Contao</a></p>'
contao-ai-cli --json content create --type list --pid 7 --set listtype=unordered \
  --set 'listitems=["One","Two","Three"]'
contao-ai-cli --json content create --type table --pid 7 \
  --set 'tableitems=[["Head 1","Head 2"],["Cell 1","Cell 2"]]' --set thead=1

# Update — repeat --set for each field
contao-ai-cli --json content update 5 --set headline="New Title"
contao-ai-cli --json content update 5 --text '<p>New text</p>'   # like create (v0.23.0)
contao-ai-cli --json page update 1 --set title="Home" --set robots=noindex

# A long or multi-line value comes from a file, not from the command line (v1.1.0)
contao-ai-cli --json page update 1 --set-file head=head.html
contao-ai-cli --json content update 5 --set-file unfilteredHtml=block.html --set invisible=0

# Publish / unpublish
contao-ai-cli --json page publish 1
contao-ai-cli --json article publish 12                     # v0.28.0
contao-ai-cli --json comment publish 7 --unpublish
```

The quoting above is for Git Bash and POSIX shells. **In Windows PowerShell 5.1 the
list, table and link examples need a different form** — see *Structured fields* below.

#### `--set-file FIELD=PATH` — a value the calling shell never has to carry (v1.1.0)

Every command that takes `--set` also takes `--set-file`, and the two mix freely. The file
is read as **UTF-8** and passed through unchanged: no trimming, no line-ending translation,
a trailing newline included. A leading byte-order mark is the one exception — it is dropped,
because PowerShell writes one by default and a BOM in `tl_page.head` would land in the
page's `<head>`. Use it for anything long or multi-line — head HTML, a block of markup, a
teaser with paragraphs.

This is not only convenience. The CLI quotes a value correctly once it has one, but
everything *before* the CLI is the caller's own shell, and carrying quotes, `$`, backticks
and newlines through it intact is the least reliable part of the chain (issue #55).
`--set-file` removes that part.

Refused, with nothing written: a field given by both `--set` and `--set-file`; the same
field twice; a file that is missing or not UTF-8.

> ⚠️ **On Windows there is a size limit, and it belongs to the whole command, not to one
> value.** CreateProcessW takes at most 32 767 characters for the entire line, so several
> `--set-file` values add up and quotation marks in markup count double (`subprocess`
> escapes every `"`). The CLI measures the line it is about to start and refuses above
> 32 000 with *"too long for Windows … Nothing was sent to the server"* — split the change
> into several commands. There is no such limit on Linux or macOS. The first version of this
> guard measured one value at a time and let 30 000 characters of HTML with 1 600 quotes
> through; it is written down because the wrong measurement looked exactly as convincing.

`--set` is no longer `required` on the update commands, because `--set-file` alone is a
complete instruction. Passing neither is still refused, and still before the connection is
opened.

| field | value | notes |
|---|---|---|
| `headline` + `headline_unit` | text, `h1`…`h6` | read back as `{"value": …, "unit": …}` |
| `listitems` | JSON array of strings | or the comma form `One,Two` when no item contains a comma |
| `listtype` | `unordered` / `ordered` | |
| `tableitems` | JSON array of rows, each an array of cells | every row the same length |
| `thead` / `tfoot` / `tleft` | `1` / `0` | first row as header, last row as footer, first column as header |

`content list --article N` returns the elements **directly** in article N. Until v0.28.0 it
filtered on `pid` alone and mixed in elements of *content element* N (nested elements, whose
parent table is `tl_content`, share the id space). Nested elements of a container:
`record list tl_content --filter ptable=tl_content --filter pid=<element id>`.

> Deleting cascades to child records — a page takes its subpages, articles and content
> elements with it. The whole set lands in one `tl_undo` entry, so it stays recoverable
> from the back end's *Restore* module. On a terminal the CLI asks first, the same as the
> Contao back end does; `--yes` skips the prompt for non-interactive use. Without a
> terminal a record delete proceeds — the record stays in `tl_undo`. Since v1.5.1 there is
> then no `[y/N]` at all, only a note on stderr (`… no terminal to ask, proceeding as
> documented; pass --yes to say so`): "terminal" means a console, and stdin on the null
> device of a PowerShell or Git Bash call — which `isatty()` takes for one — is none.
> Before, the question stood there and the delete went ahead, which read like an
> ignored "no". Pass `--yes` anyway to make the intent explicit. Since v0.29.0 this
> holds for **every** record delete, `user delete` and `member delete` included; until
> v0.28.0 those two never asked. Only `file delete` and `template delete`, which have no
> undo, refuse without `--yes` when nobody answers.

```bash
contao-ai-cli --json news delete 3 --yes
contao-ai-cli --json page delete 12 --yes
```

### Forms

`tl_form_field` is `tl_module` in miniature: 21 types, a palette each, and mandatory fields
that apply only to some of them. **Run `field-types` before creating a field** — a `submit`
needs `slabel`, a `select` needs `name` and `options`, a `captcha` needs nothing at all.

```bash
contao-ai-cli --json form field-types
contao-ai-cli --json form create --title "Contact" \
  --set sendViaEmail=1 --set recipient=info@example.com --set subject="New enquiry"
contao-ai-cli --json form field-create --form 6 --type select \
  --set name=salutation --set label=Salutation --set "options=mrs=Mrs.|mr=Mr."
contao-ai-cli --json form field-create --form 6 --type submit --set slabel=Send
```

- `recipient` and `subject` are required only once `--set sendViaEmail=1` opens that
  subpalette. A form that just stores its values needs neither.
- **`options` takes a short form** — `"mrs=Mrs.|mr=Mr."` for value and label, or
  `"red|green|blue"` when the label doubles as the value. This is the one invented
  shorthand in the CLI, and it exists because `select`, `radio` and `checkbox` are
  mandatory-options types: without it they could not be created at all.
- Fields are **appended 128 apart**, the gap Contao leaves so a later drag lands between
  neighbours without renumbering.
- **`form delete` removes every field with it.** A form is one row; a form definition is
  usually a dozen. One `tl_undo` entry for the set.

`form list` and `form fields <form-id>` answer like every other listing since v0.30.0 —
`{status, table, count, total, results}` with typed values, `--limit`/`--offset`, fields in
form order. Until v0.29.0 they returned a bare list of strings.

### Moving pages, articles and content (core-bundle v1.2.0)

When someone says "put it below X" or "put it after X", that is `move`, not `update`:

```bash
contao-ai-cli --json page move 14 --to 5        # below page 5, behind its last subpage
contao-ai-cli --json page move 14 --after 8     # directly behind page 8, same level
contao-ai-cli --json article move 21 --to 7     # onto page 7, behind its last article
contao-ai-cli --json content move 40 --after 38 # directly behind element 38, same parent
contao-ai-cli --json content move 40 --to 12 --ptable tl_news  # into news entry 12
```

A page takes its subpages, articles and content along; an article its elements. The answer
names the new `pid` and `sorting`. `--to` and `--after` are exclusive; `--ptable` goes only
with `content move --to` (default: the element's current parent table). One record per
call — to move several in order, move the first, then each next one `--after` the previous.

**Contao's rules apply, as in the back end**, and a refusal exits 1 with the reason:

- a page cannot go below itself or one of its subpages;
- **a website root (`type root`) stays at the top level, and nothing else goes there** —
  `--to 0` for a regular page is refused, and so is `page create` without `--pid` unless
  `--type root`, and `page update --set type=root` on a subpage;
- an error page (`error_401`, `error_403`, `error_404`, `error_503`) stands directly below a
  root, one of each type per root;
- the URL rules of `page update` (a page whose alias is taken in the new place is refused).

`update --set pid=…` still works and now puts the record behind its new siblings too; `move`
is the form to reach for, because it says where.

### The container a record lives in

News entries, events and FAQ questions all need a `--pid`, and until core-bundle v0.2.22
the record that `pid` pointed at could not be created. The parent commands sit in the same
group as their children, next to the listings that were already there:

```bash
contao-ai-cli --json news archives                    # the listing, unchanged
contao-ai-cli --json news archive-create --title "Blog" --set jumpTo=7
contao-ai-cli --json event calendar-create --title "Touren" --set jumpTo=12
contao-ai-cli --json faq category-create --title "Support" --set headline="FAQ"
```

Each takes `--title` and nothing else as a dedicated option. **What else is required comes
from the DCA**, so the command tells you rather than this list going stale:

- `news archive-create` / `event calendar-create` need **`jumpTo`** — the page that renders
  a single item. Without it every link the module generates goes nowhere.
- Adding `--set protected=1` makes **`groups`** required as well; it sits in that subpalette,
  so a public archive is not asked for it.
- `faq category-create` is the odd one: **`headline`** instead, and `jumpTo` is offered but
  optional. `title` is the back end label, `headline` the heading on the page — they are
  different texts as often as they are the same, and nothing derives one from the other.

**Deleting a parent takes its children with it** (`archive-delete` also removes the entries
and their content elements). One `tl_undo` entry for the whole set, so `undo restore` brings
the parent, the children and their links back in one step. If the site was visited while
the parent was gone, its list stays cached empty: the restore answers with a
`cacheWarnings` entry, and `cache clear` fixes it (core-bundle v0.28.0; Contao's list
modules do not tag a page with a container they cannot find).

**The listings filter by the parent** as `--archive`, `--calendar`, `--category`,
`--channel` — or `--pid`, the name the create commands use (v0.30.0):
`event list --pid 12`, `newsletter subscribers --pid 10`.

### A created record starts like one created in the back end

Since core-bundle v0.28.0 a create fills every field you do not set with Contao's DCA
default, as the back end does: a layout starts with the article module in the main
column, a page with `enableCanonical` and the default CSP, a subscribe, unsubscribe,
registration or password module with its mail text. **Those texts come in English** (the
console's language) — set them with `--set nl_subscribe=…` for a site in another
language. *Until v0.27.0 a subscribe module had no mail text, and the first subscription
in the front end answered HTTP 500.*

### Writes run Contao's callbacks, as in the back end (core-bundle v1.4.0)

Creating, saving, copying, moving and deleting call the DCA callbacks Contao's back end
calls (`oncreate`, `onsubmit`, `oncopy`, `oncut`, `ondelete`, and the save callbacks of the
fields you set). What extensions attach there now happens for CLI writes too:

- `page create` of a regular page gets its first article, as in the back end; the answer
  names it in `articles`. **Put content into that article** (`content create --pid <id
  from articles>`) — an `article create` afterwards leaves the page with two.
- A deleted page leaves the site search, a copied record gets what an extension copies
  along, an extension's own rules (a Consho price, a changelanguage duplicate check) apply.
- **A callback that refuses rolls the write back.** The answer is a refusal that names the
  callback; nothing was written.
- **What a callback tells the editor comes back as `messages`** (core-bundle v1.6.0):
  `[{"type": "error", "text": "…"}]` — Contao's messages (`error`, `confirm`, `new`, `info`,
  `raw`), in the answer of a success and of a refusal. A refused write prints them under
  the error, one line each (`Contao error: …`, CLI v1.5.0); a refusing callback often
  explains itself only there.
- **Virtual fields** (Contao 5.7/6.0, core-bundle v1.6.0): a field without a column of its
  own, kept in a JSON column (`jsonData`), is set and read like any field — `--set
  playerCaption=…`, and `content read` shows `playerCaption`, not `jsonData`.

Some callbacks need a back-end user. For those the core uses the user **`contao-ai`**,
created by a migration on the first update to v1.4.0: an admin that **cannot log in**
(disabled, no password) and is hidden in the back end's user list. It exists only for the
length of a callback; the operator in version and log stays the SSH user. Do not enable
it, give it a password or delete it — the migration recreates it, and the callbacks
cannot run without it.

### News, events and FAQ entries are created unpublished

As in the back end, and like pages and articles: a created entry is **offline** until you
publish it with `--set published=1` (on create or with `update`). A list module on the
site shows nothing of it before that. *Found in a practical test: an agent
created three FAQ questions, placed the list on a page, and the page was empty.*

The answer of `news`, `event`, `faq`, `article` and `newsletter create` carries the
`alias` (core-bundle v0.28.0) — the last part of the reader URL,
`/faq-answer/<alias>.html`. Read it from there; it follows the language of the page the
container points to (`Über` becomes `uber` under an English root, `ueber` under a German one).

### Event dates and times

```bash
# all day, one day — no --end-date
contao-ai-cli --json event create --pid 12 --title "Wienerwald" --start-date 2026-10-04 --set published=1
# over several days
contao-ai-cli --json event create --pid 12 --title "Wachau" --start-date 2026-10-17 --end-date 2026-10-18
# with a time
contao-ai-cli --json event create --pid 12 --title "Abendrunde" --start-date 2026-10-09 \
  --start-time 17:30 --end-time 20:00
# move it, change the time, or make it all-day again
contao-ai-cli --json event update 30 --start-date 2026-10-11 --start-time 18:00
contao-ai-cli --json event update 30 --set addTime=0
```

Dates are `YYYY-MM-DD`, times `HH:MM`, in the server's time zone. **Pass them through
these options, not through `--set`:** the event stores the moments the front end works with
(`startTime`, `endTime`) as Unix timestamps, derived from the days and times exactly as the
back end derives them — an all-day event ends at 23:59:59 of its last day (core-bundle
v0.28.0). `--set startTime=17:30` is refused by name. `--set endDate=` makes an event a
one-day event again. An all-day event gets a time only with a start time:
`event update 30 --end-time 21:00` alone is refused rather than starting it at 00:00, and
the start date cannot be emptied.

*Until core-bundle v0.27.0 an event created without `--end-date` ended on the day of the
call and was missing from "upcoming events" right away; the stored times were never
derived.*

### Cache and maintenance

```bash
contao-ai-cli cache clear
contao-ai-cli cache warmup
```

**Since contao-ai-core-bundle v0.10.0 a write invalidates the HTTP cache itself**,
the way the back end does — including `/sitemap.xml`, which Contao caches for thirty
days. The answer names what went out:

| key | present | meaning |
|---|---|---|
| `cacheTags` | when anything was invalidated | the tags, e.g. `contao.db.tl_page.12`, `contao.sitemap.1` |
| `cacheWarnings` | **only** when something failed | a callback that could not run on the console, or no invalidation service — that part of the cache may still be stale |

`cache clear` is still the way when `cacheWarnings` appears, after file writes
(`tl_files` is not covered), and against a core bundle older than v0.10.0 — there
no write invalidated anything. It rebuilds the whole container, so it is not a
reflex after every write any more.

**Shared content is covered too — do not clear the whole cache for it.** A page that
shows an element through an include (`alias` element, field `cteAlias`) carries the
*source* element's tag (`contao.db.tl_content.<id>`). Updating the source therefore
invalidates every page that includes it, on any root and any domain of the
installation — tags are purged across the whole HTTP cache, not per host. Measured
on one installation: source and alias page both cached (`Contao-Cache: fresh`), one
`content update` on the source, both answered `miss/store` with the new text right
away. Typical case: legal texts kept once and included on several domains.
Only the `alias` element was measured; for an `article` include, check the
`Contao-Cache` header before relying on it.

On a small site a needless `cache clear` costs little. On a large one it empties the
whole HTTP cache, so every page is rebuilt on its next visit, and it rebuilds the
container. **Trust `cacheTags` and reserve `cache clear` for the cases above.**

**`cache clear` is logged** (core-bundle v0.21.0, CLI v0.22.0): it runs
`contao:cache:clear`, which calls Symfony's `cache:clear` and writes *"Purged the internal
cache"* to `tl_log` (cron action, `source = CLI`, the operator) — as Contao's back end does.
The answer is `{status: "cleared", output, logged}`; `logged: false` means an older core
bundle ran the plain `cache:clear` without a trace.

### Theme export, theme import, example websites (core-bundle v1.9.0)

```bash
contao-ai-cli --json theme export 1 --to relaunch.cto          # Contao's .cto, downloaded
contao-ai-cli --json theme import relaunch.cto                  # preview only
contao-ai-cli --json theme import relaunch.cto --yes            # after the operator said yes
contao-ai-cli --json example-website import demo.sql --mode data              # preview
contao-ai-cli --json example-website import demo.sql --mode data --admins existing --yes
```

The server runs Contao's own theme manager, so ids, image sizes and file paths are mapped
as in the back end; the CLI uploads to `system/tmp` and removes the file afterwards.

- **`theme import` previews first and imports only with a yes** — at a terminal it asks;
  without one (you) the preview is the answer (`"imported": false`), and `--yes` imports.
  Show the operator the preview before you pass `--yes`: an import has no undo, creates
  records and **overwrites files** in `files/` and `templates/` (`overwrites`). Also in the
  preview: `missing_fields` (fields this database lacks — their values are dropped, Contao's
  own warning; typical when a bundle like news is missing), `lost_theme_elements` (layout
  slots that will be empty: a `.cto` holds no theme elements, Contao's import leaves those
  slots empty), and `example_websites` inside the archive, which this command does not
  import. A theme name that exists gets a number appended by Contao.
- **`theme export`** writes `<theme name>.cto` here (characters other than letters, digits, `_` and `-` become `-`) unless `--to` says otherwise; an existing
  file of that default name is not overwritten (an explicit `--to` is). Theme elements are
  not part of a `.cto` (Contao's format).
- After a theme import `nextSteps` suggests `cache clear`: Contao keeps the template
  hierarchy cached in production. Both imports take `--operator` for the system log.
- **`example-website import` can replace or empty the whole database.** `--mode` has no
  default — `full` runs every statement of the file (DROP and CREATE included), `data`
  empties every `tl_` table and runs the INSERTs, `data_no_truncate` runs only the INSERTs.
  The preview says how many tables `data` empties. A database backup is made first, always;
  the answer names it, and `backup restore <name>` is the way back — **until the next backup
  made the same day**: Contao keeps one per day (`backup_note`). When administrators exist
  and the file brings users, ask the operator and pass `--admins both` (keep them next to
  the imported ones) or `--admins existing` (keep only them); without it the command stops
  after the preview. On the same username the existing account wins; `contao-ai` is put back
  either way. `nextSteps` names what follows: `contao migrate` after `full`, `contao filesync`
  after `full`/`data` (tl_files was emptied), `cache clear`. The preview's `warnings`
  (mode `full`: empty or comment lines, which Contao runs as statements and which stop the
  import half-way) belong in front of the operator before the yes. `admins.renumbered` names
  an account that had to take a new id because an imported user holds its old one.
  If the import fails after the backup, the error names the backup and whether the
  administrators were put back — restore it before anything else makes a backup.

### Backup

```bash
contao-ai-cli backup create
contao-ai-cli --json backup list
contao-ai-cli --json backup restore backup__20261013111148.sql.gz
```

**`backup restore` restores exactly the backup named, or nothing** (v1.7.0). Up to v1.6.0 it
restored the *newest* backup on Contao 5.7 and 6.0 whatever the name: Contao reads the name
only in `interact()`, and the CLI passed `--no-interaction` (5.3 reads it regardless). Now:
no `--no-interaction`; the name must be one `backup list` shows, exactly — a miss restores
nothing and exits 1 with `available` (the ten newest names); and the backup Contao reports
as restored (`--format=json`) is compared with the name — a mismatch is an error with
`restored`, the backup the database now holds. A restore replaces the whole database —
confirm the name with the user before running it.

**Not the whole database, strictly** (v1.10.0). Contao leaves `tl_log`, `tl_search`,
`tl_search_index`, `tl_search_term` and `tl_crawl_queue` out of every backup
(`contao.backup.ignore_tables`), so a restore leaves them as they were: the search index
still lists pages of the overwritten state, some of which may no longer exist. The answer
names them in `untouched` and suggests `contao automator purgeSearchTables` in `nextSteps`
— offer it to the user, it is not run for them. `size` and `createdAt` come from `backup
list`; Contao's own answer, still in `output`, says `"size":0` after a restore.

### Schema inspection (requires contao-ai-core-bundle)

```bash
contao-ai-cli --json schema show tl_content
contao-ai-cli --json schema mandatory tl_news
contao-ai-cli --json schema resolve tl_content type
contao-ai-cli --json schema palette tl_page --set type=root --set enableCsp=1     # one kind of record
contao-ai-cli --json schema palette tl_content --set type=unfiltered_html
contao-ai-cli --json schema resolve tl_content customTpl --set type=text          # templates of a text element
```

**`schema palette` before writing to a typed record for the first time** (v1.1.0; the same
answer was `schema mandatory --set …` from core-bundle v0.16.0 on, and that spelling still
works). It answers two things at once: the `fields` this kind of record actually has, and
which of them are `mandatory`. Since v1.6.0 `--set` is optional: a table without a type
(`tl_member`) answers its one palette; a typed one asked without any `--set` answers the
selector alone, with a `hint` that names it (`tl_content chooses its palette by type: …`,
from core-bundle v1.7.0's `selectors`).

**Look up, do not guess.** A refusal of a value names the values
allowed and the command that lists them (since v1.6.0 as CLI commands — `schema resolve`,
`schema palette`). Pick from that list; do not try spellings. A value from a fixed list —
an element type, a page type, a module, a template — comes from `schema resolve <table>
<field>` before the first write (core-bundle v1.6.1 refuses an invented palette selector).

> ⚠️ **A field is not named after its element type.** Contao has *two* HTML content
> elements: type `html` stores its markup in `html`, type `unfiltered_html` stores it in
> `unfilteredHtml`, and both columns sit side by side in `tl_content`. So
> `record list tl_content --fields=html` answers an empty value for an `unfiltered_html`
> element — correctly, and there is nothing in that answer to tell "empty" from "wrong
> field". The palette is what tells you (issue #56).

**Ask for one kind of record, not the whole table** (core-bundle v0.16.0). `schema
mandatory tl_page` alone lists every field that is mandatory in *some* palette — 13 for
tl_page, from `url` (redirects only) to `csp` (only with CSP enabled). With `--set` the
server builds Contao's own palette for that record and answers only what applies: a root
page needs `title` and `language`; with `enableCsp=1` also `csp`; a redirect `title` and
`url`.

**`options` in `schema show` is a list of values or a `{value: label}` map** — never a
list of labels. A select declared `isAssociative` stores its index, so `tl_page.useSSL`
answers `{"0": "http://", "1": "https://"}` and https is `--set useSSL=1` (v0.22.1 with
core-bundle v0.21.1; before, the labels came back and `useSSL=1` was refused).

**`schema resolve` asks the installation first**, which calls the field's own options
callback — page types a bundle registers (`consho_product`) and template variants are
there. Up to CLI v0.17.0 page types came from a built-in list that could not know them;
that list is now only the fallback for an older core-bundle. Callbacks that need a
back-end user cannot run on the console: image sizes (`size`) come back empty, which
means "not known here", not "none".

**`customTpl` is checked on write** (core-bundle v0.16.0): a template Contao does not
offer for that element type is refused, and the answer lists the ones it does — or
"only the default template". Before, `--set customTpl=…/gibtesnicht` was stored and the
element silently rendered its default.

**`template delete --path templates/… --yes`** (core-bundle v0.21.0, CLI v0.22.0) deletes a
`.html.twig` below `templates/` as Contao's Template Studio does: the file, then compiled
templates and hierarchy; for a variant of a content element or front-end module
(`templates/content_element/<type>/<name>.html.twig`, `frontend_module/…`) every record
whose `customTpl` named it falls back to the default template — `migratedUsages: {table,
field, ids}`, each with a version. `undoable: false`. Like `file delete`, it needs `--yes`
unless a person types yes. Symbolic links and paths through linked folders are refused.

**A template written with `template write` is usable at once** (core-bundle v0.20.0): the
answer carries `templateCacheRefreshed: true` — Contao's template hierarchy and compiled
templates were refreshed, as the Template Studio does after saving. Up to v0.19.0 a new
variant was refused as `customTpl` and an edited override kept rendering the old version
until `cache clear`. If the refresh fails or cannot reach everything from the console
(Contao 5.3 with APCu on the web server; Twig before 3.15), the file is still written,
`templateCacheRefreshed` is `false` and `cacheWarning` says what — run `cache clear` if the
template is refused or renders the old version.

### Theme layer

```bash
contao-ai-cli --json theme list
contao-ai-cli --json layout list --theme 1
contao-ai-cli --json layout create --theme 1 --name "1 column" --template fe_page --set width=1200
contao-ai-cli --json layout update 25 --set width=90 --set width_unit=vw
```

`layout create` requires `--template` — there is no default, because the option
list depends on whether the layout is legacy (`fe_page`) or Twig, and only a
live DataContainer can resolve it. The layout arrives with no sections and no
modules; a layout without modules renders nothing.

**Put modules into a layout with `layout module-add`** (core-bundle v0.16.0):

```bash
contao-ai-cli --json layout module-add --layout 25 --module 66 --col header
contao-ai-cli --json layout module-add --layout 25 --module 0 --col main      # 0 = the articles
contao-ai-cli --json layout module-remove --layout 25 --module 66             # from every column
contao-ai-cli --json layout module-add --layout 2 --module content-317 --col header   # a theme's content element
```

`content-<id>` is a content element of the layout's theme (Contao 5.7, Themes → Content
elements; core-bundle v0.24.0) — the way to a header or footer without a module.

The server checks that the module exists and belongs to the layout's theme and, for a
classic `fe_page` layout, that the column exists (`main` always; `header`, `left`, `right`,
`footer` depending on the layout's rows and columns; custom section ids). A Twig layout's
slots come from its template and are not checked — the answer says `column_checked:
false`. Adding what is already there changes nothing (`changed: false`).

The whole list can also be written at once, as JSON — the same shape `layout read`
answers: `--set 'modules=[{"mod":"66","col":"header","enable":"1"}]'`.

> 🔴 Up to core-bundle v0.11.0 `--set modules=66` answered `ok`, stored the bare `66`
> and left the layout rendering nothing; since v0.12.0 a value that is not an array is
> refused. Before v0.16.0 the list had to be PHP-serialized by hand.

### Structured fields are read and written as arrays (core-bundle v0.16.0)

Fields Contao stores as a serialized array — `modules`, `sections`, image sizes,
`headline` and other unit fields, multi-value fields without `eval.csv`, file metadata —
come back from **every** read (`… read`, `record list`) as JSON arrays or objects:

```json
"width": {"value": "90", "unit": "vw"},
"modules": [{"mod": "70", "col": "header", "enable": "1"}],
"framework": ["layout.css", "responsive.css"]
```

**What was read can be written back unchanged, as JSON:** `--set 'size=["","","6"]'`,
`--set 'modules=[…]'`. The comma list for multi-value fields and Contao's serialized form
still work. Before v0.16.0 only `content read` unpacked `headline`; every other read
answered the raw PHP serialization.

A value that **starts with `[` or `{` but is not valid JSON is refused** (core-bundle
v0.26.0), exit 1, nothing written. Before, a list or table field stored it split at the
commas — `listitems=[Eins,Zwei,Drei]` became `['[Eins', 'Zwei', 'Drei]']` with `ok`.

> ⚠️ **Windows PowerShell 5.1 drops the double quotes inside an argument** when it calls a
> native program such as `contao-ai-cli`. Measured:
>
> | typed in PowerShell 5.1 | arrives as |
> |---|---|
> | `'listitems=["Eins","Zwei"]'` | `listitems=[Eins,Zwei]` — refused since core-bundle v0.26.0 |
> | `'<a href="https://x.y">L</a>'` (`--text`) | `<a href=https://x.y>L</a>` — **stored without error** |
> | `'listitems=[\"Eins\",\"Zwei\"]'` | `listitems=["Eins","Zwei"]` ✅ |
> | `'listitems=[\"Erster Punkt\"]'` | **split into two arguments** at the space — `Got unexpected extra argument` |
> | `'tableitems=[[\"Kopf 1\",\"Kopf 2\"]]'` | split the same way |
>
> `\"` alone is not enough (corrected in v0.28.0; the guide recommended it until then).
> PowerShell 5.1 wraps an argument in quotes only when it finds a space *outside* double
> quotes, and it counts `\"` as a quote. In JSON every space sits inside a string, so the
> argument goes out unwrapped and is cut at the space.
>
> **The form that works in 5.1 for every value: the stop-parsing token `--%`.** Everything
> after it is passed as written, so write it for the Windows command line — the whole
> argument in double quotes, inner quotes as `\"`:
>
> ```powershell
> contao-ai-cli --% --json content create --type table --pid 7 --set "tableitems=[[\"Kopf 1\",\"Kopf 2\"],[\"Zelle 1\",\"Zelle 2\"]]" --set thead=1
> contao-ai-cli --% --json content create --type text --pid 7 --text "<p>Mehr bei <a href=\"https://contao.org\" title=\"Contao CMS\">Contao</a>.</p>"
> ```
>
> Measured against a Contao 5 installation and read back unchanged. After `--%` PowerShell expands no
> `$variables` (only `%NAME%`), so put the literal values in the line. For a plain list the
> comma form needs no inner quotes at all: `--set 'listitems=Erster Punkt,Zweiter Punkt'`.
>
> Not in PowerShell 7.3+: there `$PSNativeCommandArgumentPassing` passes quotes through, so
> plain JSON in single quotes is right and `\"` would arrive as a literal backslash — refused
> as invalid JSON (7.3+ per the PowerShell documentation, not measured here). Git Bash and
> POSIX shells pass plain JSON through as well. `$PSVersionTable.PSVersion` tells which one
> runs. HTML is the quiet case: unquoted attribute values are valid HTML, so nothing refuses
> them — but a value with a space breaks. Read back what you wrote when the text contains
> attributes.

Unit fields (`width`, `headerHeight`, `footerHeight`, `widthLeft`,
`widthRight`): a plain number keeps the record's existing unit, `--set
<field>_unit=vw` changes it.

The same pattern holds for **every `inputUnit` field**, including the headline of
content elements: `--set headline="Title" --set headline_unit=h1`. The value is
checked against the field's `rgxp`, the unit against its option list — **a unit
that is not listed is refused** (`headline_unit=h9`), not replaced.

**The unit alone changes only the unit** (core-bundle v0.17.0): `content update 5 --set
headline_unit=h1` keeps the text. Before, it wrote nothing and answered `ok` with
`updated: []`.

**Resizing on upload** (`file upload` with `imageWidth`/`imageHeight` set): with core-bundle
v0.17.0 a single limit works — `imageWidth=100`, `imageHeight=0` scales width only. Up to
v0.16.0 that combination stored an **empty file** and answered `resized: true`; Contao's
back end does the same, so do not rely on one limit on an older installation.

> **Module headlines** (`module create --set headline=…`) and the other create
> commands only store a proper pair from **core-bundle v0.12.0** — before, they
> wrote the bare string and answered `ok`.
>
> 🔴 **Requires core-bundle v0.11.0.** From v0.2.28 (units) and v0.9.0 (headlines)
> up to v0.10.0 these writes failed on the server — `content create --type
> headline` and `content update … --set headline=` exited 1 with *"Not an allowed
> value … (allowed: h1, …, h6)"*, and `layout update --set width=90 --set
> width_unit=vw` with *"expected: digit"*. Check `health` before relying on it.

**`theme delete` cascades to modules, layouts, image sizes and their variants.**
Restorable as one entry, but check what you are deleting first.

### Modules

**Start with `module types`.** `tl_module` has 113 columns and 45 module types,
and what a type requires beyond a name depends on the type — a navigation needs
`pages`, a news list needs `news_archives` and `numberOfItems`, a login module
needs nothing further. `types` answers both questions at once:

```bash
contao-ai-cli --json module types
contao-ai-cli --json module list --theme 1 --type newslist
contao-ai-cli --json module create --theme 1 --name "News - Latest" --type newslist \
    --set news_archives=1 --set numberOfItems=5
```

The server refuses an unknown type and lists the valid ones; it refuses a type
whose palette wants fields you did not supply and names them. Neither guesses.

**Multi-value fields take a comma list** — `--set news_archives=1,3`, `--set
pages=2,3`. They are stored as serialized arrays, and passing a bare value used
to write a string that Contao then read as nothing at all.

**A rule on such a field applies to each entry** (core-bundle v0.14.0): `--set
playerSize=640,360`, `--set size=4,40` on a textarea form field. An image size is
Contao's triple, width, height and size ID or mode:
`--set 'size=a:3:{i:0;s:0:"";i:1;s:0:"";i:2;s:1:"6";}'` for image size 6. Up to v0.13.0
none of these could be written — the rule was held against the whole value.

**New records go behind their last sibling** (core-bundle v0.14.0) — pages, articles,
content elements, FAQs, form fields, image size items. `--set sorting=64` places one
explicitly. Up to v0.13.0 pages, articles, content elements and FAQs got `sorting` 0,
which left their order to the database.

### Image sizes

```bash
contao-ai-cli --json image-size list
contao-ai-cli --json image-size read 5
contao-ai-cli --json image-size create --theme 1 --name "Tourenbild" \
    --set width=1600 --set sizes="(max-width: 1100px) 100vw, 1000px"
contao-ai-cli --json image-size items 6
contao-ai-cli --json image-size item-create --size 6 --media "(max-width: 767px)" --set width=400
```

**Set `sizes`, not just `width`.** `width` is the fallback dimension; `sizes` is
the media-condition list the browser evaluates to choose a variant, and
`densities` is the set it chooses from. A size with a width and nothing else
serves one variant to every viewport — valid, and almost never what was asked
for.

`--theme` is required on create. Deleting a size deletes its variants with it.

### Permissions — the one place where a wrong value is silent

`user-group` writes `tl_user_group`, the record that decides what a back end editor can
reach. `member-group` writes `tl_member_group`, what protected front end content points
at.

```bash
contao-ai-cli --json user-group options
contao-ai-cli --json user-group options --table tl_news
contao-ai-cli --json user-group create --name "Editors" \
  --set modules=page,article,files --set fop=f1,f2,f3 --set pagemounts=1
contao-ai-cli --json user-group update 2 --set cud=tl_news::create,tl_news::update
contao-ai-cli --json member-group create --name "Members" --set redirect=1 --set jumpTo=7
```

**Run `options` before writing.** Everywhere else in this CLI a wrong value fails loudly
against the DCA. Here it does not: a permission field accepts any string, stores it, and
grants nothing. `--set modules=pages` (plural, wrong) reports success and leaves the group
without page access, with no error anywhere to explain why.

**A permission field is replaced, not extended.** `--set modules=page` on a group that had
five modules leaves it with one. Read the group first and write the full list you want.

`jumpTo` is required only alongside `--set redirect=1` — it sits in a subpalette, and the
command applies that rule from the DCA the same way the back end does.

Deleting a group cascades to nothing, but Contao leaves the dead ID in `tl_user.groups`
and in the `groups` field of protected content. Members lose access; nothing is cleaned up.

### Versions of a record that had its ID before (core-bundle v0.16.0)

A database can hand out the ID of a deleted record again — on some installations this happens routinely —
and `tl_version` keeps the old record's versions under that ID. `version restore` of such
a version would write the deleted record's data onto the new one.

- A create answers `earlierVersions: {"tl_image_size.7": 1}` when versions of an earlier
  record were already there.
- `version list` marks them `before_creation: true`.
- `version restore` refuses them.

Only records created through this CLI carry the marker (the first version's description
is `created`); for a record created in the back end nothing is known and nothing is
flagged. `version restore` works for every table the CLI writes versions for — before
v0.16.0 it refused 12 of them (modules, forms, themes, image sizes, archives, …) with
"Table not allowed".

### What the protocol and the answers contain

- **A created page is unpublished** (`published: false`), and so is a created article:
  publish them deliberately — a page with `page publish <id>`, an article with
  `article publish <id>` (v0.28.0; before, `article update <id> --set published=1`,
  which still works and is what `article publish` runs). A content
  element is created visible (`invisible: false`) — the unpublished article keeps it
  offline, as in the back end. *Until v0.27.0 this line said both were published with
  `page publish`; an agent working from this guide alone went looking for it (agent
  test).*
- **Only a root stores a language** (core-bundle v0.22.0). `page create --language` applies
  to `--type root`; any other page stores none and takes its root's language at runtime,
  as a page created in the back end does. Up to v0.21.1 every page stored `de`. An
  explicit `--set language=` is still written as given — the rule covers the default.
- **The operator in `tl_version` and `tl_log` is the SSH user** (e.g. `web123_ssh`), with
  `source = CLI` in the log — not a Contao back-end user. The back-end bundle passes the
  Contao user through `--operator`.
- **`tl_log.text` is HTML-encoded** (`&quot;`) — Contao encodes log input. Decode before
  parsing the JSON in it.
- **A refused create can still use up an ID.** The insert is rolled back, but the database
  counter does not go back; the next record skips a number. Nothing was written.
- **Prompts go to stderr** (CLI v0.18.0). With `--json`, stdout carries only the answer —
  before, `settings update --json` printed its confirmation question ahead of the JSON.

### Deleted by mistake — `undo`

`version restore` answers "this record changed and I want it back". `undo` is the other
half: the record was **deleted**. Every delete this CLI triggers writes a `tl_undo` entry —
for a cascade, one entry covering the parent and everything under it.

```bash
contao-ai-cli --json undo list
contao-ai-cli --json undo read 28
contao-ai-cli --json undo restore 28 --yes
```

**Run `read` before `restore`.** Records come back with their original IDs, which is what
makes references from other tables valid again — and is also the one way it fails: if
something has taken the ID since, the insert is refused and the entry stays. `read` reports
`idsTaken` and `droppedColumns` (columns the table has lost since; Contao omits them
silently, so the record comes back with less than it had).

The entry is deleted only if **every** insert succeeded. A partial restore keeps its entry
so the rest is not lost with it.

### Global settings — not a table

`tl_settings` is a `DC_File`. Its values live in `system/config/localconfig.php`, which is
why `record list tl_settings` answers "No readable columns" — correctly.

```bash
contao-ai-cli --json settings read
contao-ai-cli --json settings update --set resultsPerPage=50 --yes
```

`read` reports `value` and `persisted` separately: a setting can read `30` and be persisted
`false`, meaning that is Contao's default and nobody chose it — it moves when the default
moves.

**This is the only write that does not end in the database.** An unknown key is refused
(it would otherwise sit in the file unread forever), a mandatory setting cannot be emptied,
and the file is read back after saving to confirm the change landed.

### A table with no command of its own

Before concluding that a table is out of reach, try `record`. The per-entity groups cover
the content tables; `record` covers every table that has a DCA, which includes the
theme-level ones and anything a third-party extension registers:

```bash
contao-ai-cli --json record list tl_image_size
contao-ai-cli --json record schema tl_image_size
contao-ai-cli --json record list tl_page --filter published=1 --limit 50
contao-ai-cli --json record list tl_content --fields id,type,headline
```

The server validates the table, `--fields`, `--order` and `--filter` against the live DCA
and refuses anything else with a structured error, so guessing a column name is safe —
it fails loudly rather than silently returning the wrong thing. 20 rows by default,
100 maximum; page with `--offset`.

**Reading only.** There is no generic write. Setting a field on a table without its own
`update` command means the back end or a new command — not raw SQL, for the reasons under
*Audit trail* below.

### Every listing answers an object, not a bare array

Since v0.9.0 the `list`-style commands go through `contao:record:list` instead of writing
their own SQL. What comes back is:

```json
{"status":"ok","table":"tl_news","count":2,"total":61,"limit":2,"offset":0,
 "order":"`date` DESC","columns":["id","pid","headline"],"results":[...]}
```

The rows are in `results`. Three things follow, and all three matter more than the shape:

- **Values keep their type.** `"id": 3`, not `"id": "3"`; NULL is distinguishable from an
  empty string. The old path parsed Symfony's ASCII table by column position, so
  everything arrived as a string — and anything whose display width differed from its
  character count shifted the columns silently. That happened: a UTF-8
  umlaut once truncated a value and the command still reported success.
- **A truncated listing says so.** `count` against `total`. The server caps at 100 rows,
  defaults to 20; pass `--limit`/`--offset`. A listing that is cut off is never silent
  about it.
- **Column names are checked against the DCA**, so a wrong one is refused by name rather
  than answering something plausible.

`--limit`/`--offset` exist on every listing. `file list --path` matches a path prefix
through `--filter-prefix`, bound as a parameter, so a `%` in the value stays literal.

### Files: what the installation allows, and making it reachable (core-bundle v0.13.0)

```bash
contao-ai-cli --json file folder-create --path files/conpai
contao-ai-cli --json file upload --path files/conpai/bot.png --source ./bot.png
contao-ai-cli --json file write --path files/conpai/style.css --content @style.css
contao-ai-cli --json file folder-publish --path files/conpai          # --unpublish to protect again
```

**`file upload` takes any file the installation accepts** — images, PDFs, fonts — and sends
the local file unchanged. `file write` is for text and, since v0.25.0, sends its line endings
unchanged too (before, on Windows, LF arrived as CRLF). Both are held to the **installation's
own upload rules**, the ones a back-end upload goes through:

| rule | from | answer when broken |
|---|---|---|
| extension | `uploadTypes` | refused — `.php`, `.htaccess`, a file without extension |
| size | `maxFileSize` | refused (the old fixed 10 MB limit is gone) |
| image dimensions | `imageWidth` × `imageHeight` | resized after writing (`"resized": true`), or refused when `contao.image.reject_large_uploads` is set |
| SVG | Contao's sanitiser | scripts and event handlers removed; an unreadable SVG is refused |

`file process --allowed-types` **narrows** `uploadTypes` for one check; naming a type the
installation does not allow is refused.

**A folder is not served until it is public.** `file folder-publish` does what the back end's
checkbox does: `.public`, symlinks, a log entry. A folder that is public because a parent is
cannot be changed on its own — the command says so instead of answering `ok`.

**`file folder-create` also repairs.** Run on an existing folder whose `tl_files` record has
no UUID, it assigns one, corrects the `pid` and re-attaches direct children; `repaired`
lists what changed. Before core-bundle v0.13.0 it created every folder that way — a file
written into it hung under no parent, and `file sync` reported "No changes".

**`file move` moves a file or folder into another folder, keeping its UUIDs** (core-bundle
v0.23.0, CLI v0.24.0) — as cut and paste in the back end: `--to` is the folder, the name
stays, an existing target is not overwritten, a folder cannot go into itself.

```bash
contao-ai-cli --json file move --path files/conpai/bot.svg --to files/theme/layout
contao-ai-cli --json file move --path files/conpai/icons --to files   # into the root
```

- **Delete and write anew is not a substitute:** it gives a new UUID, and every image element
  or file picker pointing at the old one renders nothing. A move keeps them working —
  `uuidsKept: true` in the answer, checked against `tl_files` before and after.
- **`pathUsages`** lists text fields that name the old **path** (e.g. `<img src="files/…">`
  written into a text element). Those do break; fix them with `content update`. References by
  UUID (`{{file::…}}`, `{{picture::…}}`) do not. Templates and style sheets on disk are not
  searched. The list stops at 50 (`pathUsagesCapped: true`); tables whose DCA could not be
  loaded are named in `skippedTables`.
- `uuidsKept` compares the `tl_files` rows before and after — with no rows before (a file
  never synced) it is trivially `true`. Give the path in the case it has on disk.
- Refused: a path starting with a dot directly below `files/` (Contao's file sync rejects
  those), and a `.public` file — use `file folder-publish`.
- A moved folder gets its web-dir symlinks regenerated; the log has *File or folder "…" has
  been moved to "…"* with the operator. No version, no undo — as in the back end.

**`file delete` removes a file or folder with its `tl_files` records** (core-bundle v0.18.0,
CLI v0.19.0) — as the back end does: the resource, a folder's symlink in the web dir, then
the DBAFS, and a `tl_log` entry.

```bash
contao-ai-cli --json file delete --path files/conpai/alt.png --yes
contao-ai-cli --json file delete --path files/conpai/alt --force --yes   # a folder, even while used
```

- **Refused while the file is still used**, with `usages` in the answer: `fileTree` fields of
  every table with a DCA (image elements, galleries, downloads, extensions) and text fields
  containing its UUID — insert tags like `{{picture::…}}` — or its path. For a folder, every
  file below counts. **Contao's back end checks none of this.**
- `--force` deletes anyway and still lists `usages`, so the references can be cleaned up.
- **There is no undo for files** (`undoable: false`) — no `tl_undo`, no version. Check the
  answer of a run without `--force` first.
- Not searched: templates and style sheets on disk, values an extension keeps outside its
  DCA, and `tl_version`/`tl_undo` (history, not use). No usages means nothing was found in
  the database, not that nothing refers to the file.
- `files/` itself, paths outside it and `..` are refused. From core-bundle v0.19.0 the path is
  canonicalised (`files/a//b.png` is `files/a/b.png`), a symbolic link is deleted as a link
  (`type: link`) and a path through a linked folder is refused. `skippedTables` names tables
  that could not be searched; `records` counts the `tl_files` rows really removed.
- **Needs `--yes` unless a person types yes** (CLI v0.20.0). Unlike every record `delete`,
  silence at the prompt — no terminal, EOF — is a **no**: the answer is an error saying so,
  exit 1, nothing is sent to the server. Record deletes can be undone, files cannot.
- An old core bundle (before v0.18.0) is named with its version instead of a bare
  *Command "contao:file:delete" is not defined*.

`record list tl_files` shows `uuid` and `pid` as UUID strings from v0.13.0; before, the raw
bytes often came out as `null`, which looked like a missing reference.

**`page tree` is its own command** (`contao:page:tree`): the tree is built server-side,
level by level, because `record:list` caps at 100 rows and a real site passes that —
one live installation has 283 pages. Two levels by default; `truncated` says whether pages
exist below the cut, so a depth-limited tree cannot be mistaken for a complete one. Use
`--root` to descend into one branch, `--depth` for more levels.

### Page URLs, second languages, cloning (core-bundle v0.15.0)

**A page write is refused when Contao's back end would refuse it**, and nothing is
written — no version, no log entry:

- a second root with the same domain (`dns`) and URL prefix (`urlPrefix`) — an empty prefix
  counts. Domain and prefix decide which root, and so which language, 404 page and sitemap,
  answers a request.
- a second page at the same URL, e.g. `--set alias=packages` next to a page that has it.

**An empty `dns` means "any domain"**: that root answers every host no other root claims.
A single-site installation often has exactly that, so the root of `example.org` may well
have `dns: ""` — look for a root with the domain first, then for the published `fallback`
root with an empty `dns`.

**A second language is a second root on the same domain with its own prefix.** Clone the
existing tree, then translate the pages below (the clone sets the root's language in one
step, not the titles and aliases of its children).

**Ask the operator first which language is the main one** (`fallback`). Do not assume the
existing root stays it, nor that the clone becomes it. It decides which tree the
translation links (`language link`, below) point to, and which root answers a visitor
whose language matches none. A clone never becomes the main language by itself:

```bash
# root 132 is German and stays the main language, the clone becomes English
contao-ai-cli --json record clone --source-table tl_page --source-id 132 --recursive \
  --modifications '{"title":"example.com EN","language":"en","urlPrefix":"en"}'
```

If instead the **clone** is to be the main language — say root 132 is English and the
German clone shall be the main one — publish the clone, then move `fallback` from the old
root to the clone:

```bash
contao-ai-cli --json record clone --source-table tl_page --source-id 132 --recursive \
  --modifications '{"title":"example.com DE","language":"de","urlPrefix":"de","published":"1"}'
contao-ai-cli --json page update 132 --set fallback=
contao-ai-cli --json page update <new root id> --set fallback=1
```

Publish the clone before `fallback` moves: an unpublished main language answers nobody,
and a visitor whose language matches no root gets a 404. Between the two `page update`
calls the domain has no main language for a moment; run them back to back.

Contao allows **one main language per domain**. `page update` runs Contao's own check;
a clone with `{"fallback":"1"}` is refused while another root of that domain still has it
(core-bundle v1.7.4). Up to core-bundle v1.7.3 the clone copied `fallback` from its
source, so a main-language root cloned without `"fallback":""` gave the domain a second
main language, and the cloned pages were as published as their source.

**Giving the existing root a prefix checks every page below it.** A root's prefix is part
of every URL in its tree, so `page update <root> --set urlPrefix=en` runs Contao's alias
check on each page and is refused by the first one Contao would refuse, e.g.
*"Page 16: Numeric aliases are not supported!"*. The Contao demo ships its error pages with
the aliases `401` and `404`, imported past the back end. Look at the aliases of the whole
tree first, purely numeric ones in particular, and rename such pages before the prefix
change; the refusal names the page, and nothing is written.

For a root, `language`, `urlPrefix`, `urlSuffix`, `fallback` and `dns` are accepted; for any
other page only `title`, `pageTitle`, `description`, `published`, `hide`. Anything else comes
back in `ignored_modifications`. A root cloned without its own prefix or domain is refused.
Everything below is copied — articles, content, layout, CSP, `robots`. **Pages and articles
come out unpublished; content elements keep their visibility** (pages since core-bundle
v1.7.4, articles from the start, element visibility since v0.22.0), exactly as Contao's "copy with subpages" does. Pass
`{"published":"1"}` to publish the cloned root right away; its subpages stay unpublished. A hidden element stays hidden, a visible one shows as
soon as its page and article are published. Up to v0.21.1 every cloned element was hidden,
and a published clone showed an empty page. Subpages store no language; the root keeps its
own or the one from `--modifications`.
Cloned pages get Contao's alias from the title (`startseite-kopie`), titles get
" (Kopie)"; translate both afterwards with `page update`. **With folder URLs** (`useFolderUrl`
on the root) the alias carries the path: `top-menu-folder-kopie/logout-kopie`. Set each
page's alias explicitly, flat or as the path you want; do not expect the short form. The
cloned root goes behind the last root.

The answer counts the pages in `page_count`, the root included (core-bundle v1.9.1).
**`count` is the number of articles**, kept from the shape of the other cloners; a tree of
42 pages with 40 articles answers `"count": 40`. `subpage_count` leaves the root out.

**Archives, forms, newsletter channels, modules and layouts clone too**, for the parts of a
second language that are not pages:

| `--source-table` | comes along | not taken from the source |
|---|---|---|
| `tl_news_archive`, `tl_calendar`, `tl_faq_category` | their entries with their content elements, each entry **unpublished** | nothing — and **no `references`**: the archive's `jumpTo` (the reader page) stays on the source's page without being named |
| `tl_form` (v1.8.0) | all fields, in their order | `alias` (new from the title), `formID` (empty) |
| `tl_newsletter_channel` (v1.8.0) | its newsletters, each unsent and with a new alias | the **recipients**, unless `--with-recipients` |
| `tl_module`, `tl_layout` (v1.8.0) | — | nothing; the clone stays in the same theme |

Only the name is taken from `--modifications` (`title` for archives, calendars, FAQ
categories, forms and channels, `name` for modules and layouts). **References stay as in the source**: a cloned form still redirects to
the same `jumpTo` page, a cloned layout shows the same modules. The answer lists those
fields in `references`; point them at the new language with `form update`, `module update`,
`layout update` or `newsletter channel-update`. **`references` is a hint, not the list to
work from:** it names fields that point at records, not text with insert tags, and up to
core-bundle v1.9.0 it left out a news list's `news_readerModule` and listed `reg_homeDir`
on modules that hold sixteen zero bytes there (every module of the Contao demo). Your own survey (below) is the list. `not_copied` names what was reset on the
cloned record itself (child rows are not listed). `children` counts the copied child rows
per table; modules and layouts have none, and the key is absent there.

```bash
# German copy of newsletter channel 3, without its recipients
contao-ai-cli --json record clone --source-table tl_newsletter_channel --source-id 3 \
  --modifications '{"title":"Newsletter DE"}'
contao-ai-cli --json newsletter channel-update <new id> --set jumpTo=<German page id>
```

**Ask the operator before `--with-recipients`.** Contao's own copy takes the recipients
along, this one does not: they consented to the source channel, and after a clone into
another language they would receive newsletters they never subscribed to. Copied recipients
keep `active` and come out without `addedOn`, so Contao lists them as added manually. The
answer says which it was in `recipients_copied`.

Since v1.10.0 the CLI asks too: at a terminal a person answers; **without one — which is
you — `--with-recipients` stops with "Nothing was cloned" unless `--yes` comes along.** Ask
the operator in your conversation first, then pass both. Never add `--yes` on your own to get
past the refusal. The same holds for `bridge clone --with-recipients` (backend-bundle
v0.19.0): the CLI asks, the server does not ask again — over the bridge the token counts
as the user's consent, so the question you put to the operator is the only one there is. A backend before v0.19.0 drops the
flag; the answer then carries a `warning` that the clone has no recipients. In the back-end
chat the server itself asks before it copies them.

**A whole theme** (core-bundle v1.9.0): `record clone --source-table tl_theme --source-id
<id>` copies its modules, layouts, image sizes and theme elements, and points the copies at
each other — the module list of every layout, root-dependent modules, reader modules, theme
element aliases, image sizes. **Contao itself has no theme copy in the back end** (only
export and import of a `.cto` file), so tell the user this is a step the CLI adds; the
answer carries the same sentence in `note`. References out of the theme stay: no page uses
the copied layouts until someone assigns them, so the clone changes nothing on the site by
itself. `remapped` says what was bent
(`"tl_layout.modules": 5`), `references` what still points out (the template folder in
`templates` is shared, not copied). The name is `<name> (Kopie)`, counted on when taken;
`--modifications '{"name": "…"}'` with a name already taken is refused.

```bash
contao-ai-cli --json record clone --source-table tl_theme --source-id 1 \
  --modifications '{"name":"Relaunch 2027"}'
```

**A create without an alias gets Contao's alias** (core-bundle v0.17.0) — pages, articles,
news, events, newsletters, and FAQ questions from core-bundle v0.28.0: from the title, with
the language and allowed characters of the root. Every one of these answers with the alias
from core-bundle v0.28.0; before, only `page create` did. `page create --title "Über uns"` under a German root answers `"alias": "ueber-uns"`;
up to core-bundle v0.16.0 it was `über-uns`. Read the alias from the answer instead of
predicting it. If Contao's rule cannot run, the old slug is used and the answer carries
`aliasWarning`.

**`routeConflicts` in the answer of `page create`/`page update`** (core-bundle v0.20.0): pages
on the same domain whose URL may collide with this one, `[{id, title, alias, path}]` — the
hint Contao's back end shows under the alias field ("the following pages have a similar
alias that may conflict"). **A hint, not a refusal:** Contao saves such a page too, e.g. a
second `index` under the same root. Tell the user; usually one alias should change. A
taken URL like a second `packages` is still refused. With `--ids` the bulk answer reports
them per record: `routeConflicts: {"176": [...]}`.

Aliases may repeat **across** roots — `index` under `example.com` and under `example.com/en`
are different URLs. For a shared layout, use a `navigation` module (it follows the current
root) rather than a `customnav` with fixed page IDs, and switch languages with
`{{iflng::de}}…{{iflng}}` in an HTML module.

**`listing data` goes through the server since v1.10.0** (core-bundle v1.9.0,
`contao:listing:data`). `list_where` is a free SQL fragment stored in the listing module,
so the query is configured in the site rather than by the caller; the server now runs it
as the module does — with its sort (`list_sort`) and insert tags — and answers
`{status, module, table, count, total, limit, offset, columns, results}`, sensitive fields
masked. `--limit` (default 100, at most 1000) and `--offset` page through it. Against an
older core-bundle the CLI falls back to its own SQL, as before: values as strings, sorted
by `id`, no paging. A module that is missing, is no listing or has no table configured is
an error (exit 1) either way.

⚠️ **All listings now need contao-ai-core-bundle on the target.** They used to run through
`doctrine:query:sql`, which is plain Contao.

### Changing a text on a site with several languages

`content find` names each element's root and its `language`. When the user quotes a
text, change the element that shows **that** text, in its language — not the
counterpart in the language the user writes in. Then ask whether the translations
should follow; do not translate them silently (in one case a German request
about the English "A powerful CMS" changed the German element first, translated).

### Translation links: `language link` and `language check` (core-bundle v1.4.0)

With **terminal42/contao-changelanguage** installed, the language switcher knows which
page, article, news item, event or FAQ is the translation of which. Cloning a second
language (above) does not set these links; `language link` does:

```bash
# the EN page 201 is the translation of the DE page 1
contao-ai-cli --json language link --table tl_page --id 201 --main 1
# an archive first, then its entries
contao-ai-cli --json language link --table tl_news_archive --id 6 --main 4
contao-ai-cli --json language link --table tl_news --id 4 --main 3
# remove a link
contao-ai-cli --json language link --table tl_page --id 201 --main 0
# what is missing or broken, per root of another language (reads only)
contao-ai-cli --json language check --root 83
# the linked versions of one record, each with root and language (core v1.11.0)
contao-ai-cli --json language versions --table tl_article --id 36
```

- **Before saying anything about other languages, look:** `language versions` for a page,
  article, news item, event or FAQ; `content find` names the versions of each hit's page
  and article itself (`versions.page`, `versions.article`; for an element of a news item
  or event `versions.entry` — core v1.11.0). `otherRoots` is always in the answer; an
  empty `versions` list means nothing is linked, not that no other language exists — a
  version may be there without a link (`note`). Without changelanguage, on a site with
  several roots, `content find` says so in `versionsNote`. Change the version the user
  means; ask before touching the others.

- **The order matters, as in the back end:** a page before its articles, an archive
  before its entries. The target must be one the back end would offer: for a page, a page
  in the tree of the fallback root; for an article, news item, event or FAQ, one of the
  entries the back end lists for the linked page or archive — and those lists contain
  only what changelanguage finds, which skips unpublished pages. A second link to the
  same target is refused by the package's own check. A refusal says which rule failed —
  since core v1.11.1 also which page or root is unpublished when an article has no target.
  `language check` lists such articles apart (`unlinkableArticles`, with the reason): they
  cannot be linked until that page is published, here or in the back end. Do not try.
- The write goes through the core: version, the package's own checks, cache invalidation.
- Without the package on the server the group answers that the command does not exist.

### Adding a second language — the whole sequence

The two sections above give the building blocks. This one gives the order, and the places
where the first language survives the clone without anything failing. Tried end to end on
the Contao demo (42 pages, about 200 content elements, EN → EN + DE) with core-bundle
v1.7.3, when modules and layouts still had to be rebuilt by hand: about 35 minutes of
writes, under an hour with the survey and the checks. The clones below shorten that. It
needs core-bundle v1.8.0 for the clones of forms, channels, modules and layouts, v1.9.0 for
a theme copy, and v1.4.0 with changelanguage on the server for the translation links.

> 🎯 **The page tree is the smallest part.** One `record clone` copies it. The work is in
> everything that points at fixed IDs of the first language — modules, layouts, insert tags,
> archives, forms — and none of it fails when left alone: the second language simply shows
> links, news and texts of the first.

**1. Ask the operator before anything is written.** These are decisions, not facts you can
read from the site:

| Question | Why it is not yours |
|---|---|
| Which language is the main one (`fallback`)? | It decides which root answers a visitor whose language matches none, and which tree the translation links point to. Never assume the existing root stays it |
| Prefix for both languages, or only for the new one? | Changes every existing URL when the main language gets one too |
| Same theme, or a copy of the theme? | See below. Propose the same theme |
| Everything, or navigation and start page first? | Newsletters, forms, FAQ are a lot of text |
| Recipients of a newsletter channel along? | Only with consent, see `--with-recipients` above |

**Same theme or a copy.** The usual way is **one theme**: the layouts and
modules that need a version per language are cloned inside it (`record clone` of
`tl_module`/`tl_layout` keeps the clone in the same theme), everything that follows the
current root stays shared. A theme copy (`--source-table tl_theme`) gives each language
its own set, and every later design change has to be made twice. Ask; do not pick the
copy because it is one call.

**2. Survey — find every reference to a fixed ID.** Read, write nothing. Page through with
`record list --fields … --limit 100 --offset …`:

- **Modules:** `jumpTo`, `rootPage`, `pages` (custom navigation), `news_archives`,
  `cal_calendar`, `faq_categories`, `nl_channels`, `news_readerModule`, `cal_readerModule`,
  `rss_feed` (feed reader), `rootPageDependentModules`, and text in `html`, `headline`,
  `nl_subscribe`, `nl_unsubscribe`, `reg_password`
- **Content elements:** `module`, `form`, `cteAlias`, `articleAlias`, `article` (teaser),
  `url`; and text beyond `text` and `headline`: `linkTitle`, `titleText`, `summary`,
  `playerCaption`, `data`, `tableitems`, `listitems`
- **Form fields:** `label`, `options`, `help`, `placeholder`, the submit button's `slabel`
- **Insert tags in every text field**, HTML modules, table cells and list items included:
  `{{link_url::N}}`, `{{link_title::N}}`, `{{link_open::N}}`, `{{article_url::N}}`,
  `{{insert_article::N}}`, `{{insert_content::N}}`. Structured fields come back as arrays
  (see "Structured fields are read and written as arrays"), so search the JSON answer as
  text, not only the plain columns
- **Layouts:** the module list, `newsfeeds`/`calendarfeeds`, text in `script` (ARIA labels)
- **Pages:** `layout` (also where "assign a layout" is off — the clone copies it), `jumpTo`
  (redirect and logout pages), `pageTitle`, `description`; feed pages (`news_feed`,
  `calendar_feed`) also `newsArchives`, `eventCalendars`, `feedDescription`
- **Archives, calendars, FAQ categories:** `jumpTo`, the reader page of their entries

An insert tag pointing at a page that does not exist is a fault of the site, not of the
clone — report it to the operator rather than inventing a target.

```bash
contao-ai-cli --json record list tl_content --fields id,pid,type,module,form,cteAlias,articleAlias,article,url --limit 100
contao-ai-cli --json record list tl_module --fields id,name,type,jumpTo,rootPage,pages --limit 100
```

Keep the result as a list; every later step works through it.

**3. Then in this order:**

1. `backup create`
2. Install changelanguage if the operator wants a language switcher (see "Installing an
   extension this CLI does not manage"), then `contao migrate` — the package adds columns,
   and without them `language link` fails — and `schema sync <table>` for each table it
   extends (`tl_page`, `tl_article`, the news, calendar and FAQ tables, `tl_module`; one
   table per call)
3. Clone the page tree (see "Page URLs, second languages, cloning"). Build the mapping
   old → new from tree position and `sorting`: pages, then articles per page, then elements
   per article. `page tree --root <id> --depth <n>` shows both trees side by side. Every
   following step needs the mapping
4. Clone archives, calendars, FAQ categories, forms, newsletter channels. Forms and
   channels list what still points back in `references`; **archives, calendars and FAQ
   categories do not** — their `jumpTo` stays on the first language's reader page without
   a word, so the new language's news links lead into the old tree
5. Modules and layouts: in the same theme, clone only those with a per-language reference
   or text from step 2 — reader modules before the lists that point to them — and leave
   shared what follows the current root: `navigation` without `defineRoot`, `breadcrumb`,
   `articlenav`, `search` without `jumpTo`. With a theme copy, its layouts are already
   there. **Either way, assign the new layouts to the new pages** (`page update --set
   layout=…`): every cloned page still carries the source's layout, and the new tree renders
   with the first language's footer, forms and HTML modules.
   *Without layout copies:* Contao's module type `root_page_dependent_modules` shows a
   different module per website root (`rootPageDependentModules`, `{"<root id>": "<module
   id>"}`). Put one of those into the layout where a module differs per language, and both
   trees keep one layout — fewer copies to keep in step later. Propose it when the layouts
   would differ only in their modules:

   ```bash
   contao-ai-cli --json module create --theme 1 --name "Footer EN/DE" --type root_page_dependent_modules \
     --set 'rootPageDependentModules={"1":"12","76":"13"}'
   ```
6. Repoint every reference from step 2 at the new IDs: `module update`, `layout update`,
   `content update`, `page update`, `form update`, `newsletter channel-update`,
   `news archive-update`, `event calendar-update`, `faq category-update`
7. Translate pages (`title`, `alias`, `pageTitle`, `description`), articles (aliases are
   unique across the site, give them their own), elements, entries — and rewrite the
   insert tags in the same pass
8. File metadata, see below
9. If the main language gets a prefix now: look for purely numeric aliases in its tree
   first, then `page update <root> --set urlPrefix=…`
10. Publish the new pages, articles and entries; a clone leaves them unpublished. If the
    operator chose the **new** language as the main one, move `fallback` now (see "Page
    URLs, second languages, cloning": old root off, new root on, back to back)
11. `language link` page by page, then articles, then archives, then entries. The target
    (`--main`) always lies in the tree of the main language: with the existing root as main
    language, link the new records to the old ones; with the new one as main language, the
    other way round. Then `language check --root <root that is not the main language>`.
    An article on an **unpublished** page (a folder like `_Resources` holding included
    header and footer articles) cannot be linked, as source or as target; `language check`
    lists it as unlinked. That is harmless — such articles are not reached through the
    switcher — and needs no workaround
12. Language switcher, then the checks at the end; remove every copy you made on the
    server along the way (`composer.json` backups in `/tmp`, exported lists)

**Texts that stay in the first language without being in the tree:**

- **File metadata.** Images, galleries, downloads and video posters take alt text, title and
  caption from the file manager (`tl_files.meta`, per language) unless the element has
  `overwriteMeta`. **A missing language falls back to the main language silently**: the
  German page shows the English alt text, and nobody sees it, because alt text is
  invisible. Collect the files used by elements with `overwriteMeta` off (theme elements
  and the logo included) and add the new language to each one that has text:

  ```bash
  contao-ai-cli --json file meta --path files/theme/logo.svg --lang de --set "alt=…" --set "title=…"
  ```

- **Default texts.** A created module gets its mail texts in the console's language (see
  "A created record starts like one created in the back end"); a cloned one keeps the
  source's. Translate `nl_subscribe`, `nl_unsubscribe`, `reg_password` either way.
- **Names that the front end shows.** A newsletter channel's title appears in the
  subscription form; a form's field labels and options are text too.

Two things that look like remnants and are not: the newsletter list of the new language
stays **empty**, because cloned newsletters are unsent and only Contao's real dispatch sets
`sent` (see "The newsletter does not send"); and "Do not fill in this field", the hidden
honeypot field of the captcha, may stay English — the text comes from Contao's core, not
from the site.

**The language switcher** is the module `changelanguage`; it has no required fields beyond
the name. **It comes unstyled**: a bare list, the entries one below the other, in the
colours of whatever surrounds it — on a dark footer, possibly unreadable. Give it the CSS
classes the theme's own meta navigation carries (read the module or element that renders
it, `cssID`), so it looks like part of the site without new CSS; on the Contao demo that is
`nav-meta nav-meta--header` at the top and `nav-meta nav-meta--footer` in the footer. Then
check the theme's CSS for breakpoints that hide that area: the demo hides its top bar on
small screens, so a switcher placed there alone vanishes on a phone. A second one in the
footer was the fix there.

**Checks at the end — in the browser, not only in the answers:**

- every link of the new start page answers 200
- the switcher leads to the translation on subpages and on news and event detail pages,
  in both directions
- the visible text of the new language holds no rest of the first (channel names, button
  labels, ARIA labels)
- `robots`, the sitemap and `health` as before
- **look at it, desktop and mobile.** No answer describes the rendering; the vanished
  switcher above was found only by looking

## Available command groups

`article`, `backup`, `bridge`, `cache`, `comment`, `contao`, `content`, `debug`, `event`, `faq`, `file`, `form`, `layout`, `listing`, `mailer`, `member`, `member-group`, `messenger`, `news`, `newsletter`, `page`, `record`, `schema`, `search`, `security`, `settings`, `template`, `undo`, `user`, `user-group`, `version`

Standalone commands: `connect`, `guide`, `health`, `repl`, `self-update`, `session-delete`, `session-list`

Run `contao-ai-cli <group> --help` for the subcommands of a group; the full table is in
[README.md](README.md) and is generated from the command tree, so it cannot go stale.

### Commands this CLI does not wrap: the `ext` group

An extension — someone else's, or your own site bundle — registers its own
`contao:*` console command with Symfony. It exists on the server, and until now
nothing here could learn that it does.

```bash
contao-ai-cli ext list                      # what this installation has that the CLI has no command for
contao-ai-cli ext describe contao:x:y       # its arguments, options and help, read off the server
contao-ai-cli ext run contao:x:y --flag     # run it
```

`ext list` asks the server what exists and subtracts what this CLI wraps. The
subtraction happens here on purpose: what the CLI wraps is the CLI's business,
and a copy of that list on the server would drift from the original.

**`ext run` starts commands under `contao:`, and others only with an `#[AiContract]`
(next paragraph).** Everything else — the framework's own namespace, and a site bundle
that registered its command elsewhere without one — is listed under `out_of_reach` and
can be described, but not run.
`doctrine:query:sql` is the reason: a generic runner that reaches it puts every
DCA rule, version and log entry back on the honour system. The boundary is on
running, not on naming, so nothing is hidden from the listing.

**A command outside `contao:` becomes reachable by declaring an `#[AiContract]`.**
It does not have to rename itself, and should not: a prefix of its own is the
convention — `cookiebar:` is a published Contao extension, and Symfony's own docs
suggest `app:` — while `contao:` is someone else's property. The prefix says who
wrote a command; only the declaration says whether its author meant it to be
driven from here.

**`ext run` warns, and the server records the invocation before starting the
target.** Both, deliberately: the warning reaches you before the effect, the log
entry reaches whoever asks afterwards what happened. The entry says what was
*started* — a foreign command may write without leaving any trace of its own, so
the one thing that can be promised is the smaller one.

**`--operator` reaches the command, not only the log entry** (core-bundle v1.7.1). A
command that records who changed something — `tl_version`, its own history — defines
an `--operator` option that takes a value; `ext run --operator <user>` hands the user on
to it. Setting `--operator` inside the command line as well is refused unless it is
exactly the same user. With an older core bundle the name goes into the log entry only.

**Values with spaces, line breaks, quotes or backslashes arrive whole** (v1.8.2). Pass
them as one shell argument, as for any command — `--set "title=Zwei Wörter"`, or a list
value with a line break. The CLI quotes each such token the way the server's
`StringInput` reads it back. Up to v1.8.1 the tokens were joined with a bare space and
such a value fell apart into several arguments (*Too many arguments*); nothing was
written. Don't add your own quotes inside the value: they would arrive as part of it.

**`ext run` passes nothing on STDIN, and secrets never go through contao-ai.** A command
that reads STDIN gets an empty input and answers at once with its own message. Codes,
passwords and keys belong to a person typing them over SSH (`php bin/console <command>
< codes.txt`), not to an agent: to hand one on, it would have to sit in the agent's
context. Up to v1.9.0 such a command waited for the 60-second timeout on Windows:
Windows' own `ssh.exe` never passed the end of an empty input on to the server. Every
command of this CLI was affected, not only `ext run`.

Two refusals, and they are not the same kind:

- **A command this CLI wraps is refused here.** Not for safety — it would run
  fine — but because the wrapper converts fields, checks them against the DCA
  and shapes the answer. The bare command would answer differently under the
  same name, and which one you got would depend on how you asked. Use the
  dedicated command.
- **Anything outside `contao:` is out of reach**, `doctrine:query:sql` above all.
  A generic runner that reaches it would put every DCA rule, version and log
  entry this bundle writes back on the honour system — through the very tool
  built to end that. This is not a security boundary: whoever calls this has
  shell access. It bounds what the tool does on its own.

**The foreign command's answer comes back in an envelope**, because its shape is
unknown by definition — a plugin can answer `"status": "ok"` and have done
nothing, or exit non-zero while its own JSON still reads fine:

```json
{ "status": "error", "command": "contao:demo:ping --nosuch",
  "wrapped": false, "exit_code": 1,
  "command_output": { "status": "error", "message": "RuntimeException: …" } }
```

Read `status` as **this CLI's verdict on the run**, derived from the exit code
alone. Everything the command itself said is under `command_output`, untouched,
and nothing it says can reach the top level — for a wrapped command the CLI
knows the shape because the core bundle produces it, and here it does not.

The process exits non-zero when the foreign command failed, so a shell loop
around `ext run` cannot read success from a failed run. `stderr` appears **only
on failure**: its absence means the run succeeded, not that stderr was empty.

A failed run may also carry a **`hint`** field, and `ext describe` appends the
same sentence to its error. It answers the question a missing command raises —
*is this server's bundle too old, or does the command not exist at all?* Both
are said explicitly, and they are not the same claim:

```
"contao:page:tree" is missing on this server, which runs contao-ai-core-bundle
v0.2.14; v0.2.33 is available. …
```
```
This server runs contao-ai-core-bundle v0.2.33, so the version is not the
reason — "contao:x:y" does not exist in that bundle at all.
```

"The version was checked and excluded" and "the version could not be read" are
worded differently on purpose, so neither can be mistaken for the other. When
nothing is known, no `hint` appears.

**A command may declare a contract, and then the warning says what it declared.**
An extension can carry an `#[AiContract]` attribute (see the core bundle's README);
`ext describe` returns it under `contract` and `ext run` prints it before running:

```
  tables        tl_shop_order, tl_shop_voucher
  writes        yes
  trail         tl_log kept 7 days, written before the run
  hands off     tl_shop_order — the transitions hang on save_callbacks

  IRREVERSIBLE  sends a confirmation mail to the customer
```

Read it as the command's own word. Nothing in this CLI checks any of it, and the text
says so — the wrapped commands' guarantees still do not apply. Four things are worth
treating differently:

- **`IRREVERSIBLE`** is the line to stop at. A database write has `tl_undo`; this has
  nothing, and no part of this CLI can take it back.
- **`hands off`** is the extension saying a generic writer must not touch that table,
  usually because its transitions hang on DCA callbacks. It holds for a future dedicated
  wrapper too, not only for a generic path.
- **The retention** beside a trail is read from the installation, not declared. `tl_log`
  and `tl_version` are 7 days against 90, so "leaves a log entry" and "leaves a version"
  are not interchangeable assurances.
- **`trail  none`** (since v1.4.1) is a statement: the command declared `trace: []`, it
  leaves no trail. No `trail` line at all means the command did not say — not the same.

When a command declares nothing, the older blanket warning applies unchanged — that is
the normal case, not a fault.

### The newsletter does not send

`newsletter send` exists as a command and **always refuses**. This is a decision, not a
gap — so do not look for another route.

Contao's send routine is browser-driven: each cycle ends with a JavaScript timer that
loads the next batch, so it cannot run outside a back-end session at all. And a mail that
has gone out cannot be taken back, which is the only thing in this CLI that is true.

**The route to avoid is `sent=1`.** Setting `tl_newsletter.sent` sends nothing. It marks
the newsletter as sent *and publishes it in the front end archive*, because the reader
lists exactly the records with `sent=1` — a state no back-end action can produce. The core
bundle refuses writes to `sent` and `date` on both create and update for that reason.

Everything else in the module is available: `channel-create/update/delete`,
`create/update/delete`, `subscriber-create/update/delete`. Sending is what a person does
in the back end: *Newsletters -> channel -> send icon*.

`subscriber-create` defaults to creating an **inactive** recipient. Without a terminal to
answer, `--active` has to be passed explicitly — double opt-in guards Contao's front end
subscribe module, not this table, so the consent is the operator's and the activation is
made explicit rather than assumed. The command also applies the rules of Contao's own CSV
import: valid address, no duplicate in the channel, and not on the channel's deny list.

Full CRUD support requires [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle)
to be installed on the target Contao site. The `bridge` group additionally needs
[contao-ai-backend-bundle](https://github.com/webwerkwien/contao-ai-backend-bundle) — it is the
only group that does; everything else runs over SSH against the core bundle.

## Multiple installations

```bash
# Connect to multiple sites with named sessions
contao-ai-cli connect --host site-a.example.com --user deploy --root /var/www/a --name site-a
contao-ai-cli connect --host site-b.example.com --user deploy --root /var/www/b --name site-b

# Session files live at ~/.contao-ai-cli/<name>.json
# Without --session the CLI uses the session named "session" -- never the first available
contao-ai-cli --session site-a --json page list
```

Until v0.28.0 this block said the first available session was loaded automatically. It
never was: an agent following it failed on its first command (agent test).
Choosing a site by default would be the wrong fix — with several live sites in the list,
the one a command writes to has to be named.

## Audit trail

Every write leaves a trace on the server. Nothing here is optional or configurable —
it is worth knowing because it means a change can be found and undone later.

**Contao's system log (`tl_log`)**, visible in the back end under *System → System log*,
one row per successful write:

| Column | Value |
| --- | --- |
| `source` | `CLI` — Contao writes only `BE` and `FE` itself, so CLI writes are filterable on their own |
| `action` | `GENERAL` for records, `FILES` for file, folder and template commands |
| `username` | the SSH user of the session |
| `func` | the command name, e.g. `contao:page:update` |
| `text` | the command name plus the JSON payload the command returned |

Two caveats. `tl_log` is purged by Contao's cron after **7 days** — it answers "what
happened this week", not "who changed this in May". And failed commands are not
logged, because a rejected `--set` changed nothing.

**Version snapshots (`tl_version`)** are the durable trace, for every table whose DCA
keeps versions (`enableVersioning`), written by Contao's own `Versions` class since
core-bundle v1.4.0 — the same entries the back end writes, with the SSH user as author and
a link to the edit form. Deletions additionally land in `tl_undo` and stay restorable from
the back end's *Restore* module.

**`version restore` since core-bundle v1.4.0** runs Contao's restore: the record stays
where it is (before, it moved back to the parent and position it had then), and an
extension can refuse — Consho does for its order tables. A refusal changes nothing.

### None of it happens if you go around this CLI

Read the table above as a description of **what this CLI writes**, not of what the
server records on its own. The server records nothing. Change a row with `mysql`
over the same SSH connection and there is no version, no undo entry and no log
line — only an empty version list that nobody thinks to check. There is no error
and no warning; the change simply has no history.

This is worth stating because the shortcut is always available and always faster
to type. **Every user of this CLI has SSH access — the CLI cannot work without
it**, and the session file names the host, the user and the Contao root. So the
way around the audit trail is not an exotic mistake: it is one line, and it looks
like it worked.

A second reason, independent of the audit trail: **serialised columns break
silently under raw SQL.** A headline is stored as
`a:2:{s:5:"value";s:28:"…";s:4:"unit";s:2:"h1";}`. A `REPLACE()` changes the text
but not the byte count in front of it, and the record is unreadable afterwards.
The DCA layer these commands go through gets that right.

**Reading is fine.** `SELECT`, `SHOW` and `mysqldump` change nothing and are often
the shorter path — use them freely. The rule is about writes:

| | |
| --- | --- |
| `UPDATE` / `INSERT` / `DELETE` / `ALTER` / `TRUNCATE` | through this CLI |
| `SELECT` / `SHOW` / `mysqldump` | raw SQL is fine |

Requires contao-ai-core-bundle **v0.2.13** or newer on the target site; older versions
wrote nothing to `tl_log` at all. `contao-ai-cli health` shows the installed version.

## Error handling

- All commands exit with code `0` on success, non-zero on failure: `1` for a failed
  command, `2` for a usage error (missing argument, unknown option or command). A missing
  session file is `2` for the commands that need the core bundle and `1` for the others
  (`cache`, `backup`, `schema`, …).
- With `--json` — before or after the command — an error is **one object on stdout** and
  nothing else on stderr except the error report for unexpected failures (below)
  (v0.28.0):

  ```json
  {"status": "error", "code": 1, "message": "Command failed (exit 1): contao:page:read 198\nPage not found: 198"}
  ```

  `code` equals the exit code. Until v0.27.0 this line promised `{"error": "..."}` while
  every command answered `Error: ...` as plain text on stderr (agent test).
  Without `--json` it is still that `Error: ...` line on stderr. Commands that already
  answered their own failures as an object (`connect`, `bundle`, `file`, `template`,
  `ext run`, `bridge`, `self-update`) keep that answer.
- SSH timeouts default to 60s; composer operations use 180s internally

### Error reports (since v0.16.0) — and what you must not do with them

When something fails **unexpectedly**, the CLI writes a report to stderr under
the usual `Error: …` line, headed `## Fehlerbericht contao-ai`. It contains
versions, the exception class, our own file and line, and the (masked) message.
Exit code and stdout are unchanged, so nothing about parsing output changes. Under
`--json` the report stands alone on stderr and the error object is on stdout.

> ⚠️ **Do not pass a report on without asking the user first.**
>
> Not by mail, not into an issue, not into a chat — even when the user's earlier
> instruction sounds like it covers it ("fix my errors", "report problems to the
> maintainer"). Ask for this report, this time, and show it before sending.
>
> The report is generated because something broke, which is exactly the moment
> the masking is least able to promise anything: `CredentialMasker` is a pattern
> net, and a pattern net does not know what a secret looks like in a message
> nobody anticipated. The user is the one who can tell whether the text is safe
> to hand over. That judgement is theirs, not yours.

**A report is only produced for defects.** A 4xx from the bridge, a record that
does not exist, a permission that refused, a wrong session name — those are
*answers*, and they get no report.

**A crash inside a core command is a defect too** (v1.3.0, with core-bundle v1.3.0).
The core then adds `"exception": "<ShortClassName>"` to its error answer; the CLI keeps
it on `ContaoBackendError.defect`, writes the report with the row `ausnahme.server`, and
under `--json` the error object carries `"exception"` as well. A refusal has no such
field — the core throws refusals as `\InvalidArgumentException` and marks everything
else. Up to v1.2.0 a failed query and "page not found" were the same plain `Error:` line.
`cache clear` and `user create` (when the password step fails) carry it along too. Commands
that pass the core's answer through as it came (`file delete`, `file move`, `template
delete`, `page move`, `article move`, `content move`, a bulk update's summary) keep the field
in that answer. If you see one, something is genuinely broken
in this software, and it is worth telling the maintainer about (with consent).

**What to do with it:**

1. Show the user the report and ask whether it may be passed on.
2. If yes and you have mail: send it to the maintainer.
3. If yes and you have GitHub: open an issue on the relevant repo.
4. Otherwise: hand it over as a copyable block and let the user decide.

Do not summarise it or retype parts of it — the value is in the exact versions
and line numbers. Pass it verbatim, or not at all.

## Security notes

- Session files contain SSH connection details — treat them as credentials
- The CLI never stores passwords; use SSH key authentication
- Always maintain a current backup of the Contao installation before making changes

### A bulk update that partly failed now exits non-zero (since v0.15.0)

`--ids` / `--ids-from-file` used to end with exit code 0 even when the server
reported *"1 of 2 records failed"*. It now exits 1, and **the JSON summary is
still written to stdout** — read it, it names the failed ids and why.

So: parse stdout as before, and stop treating a zero exit as "all of them
worked". If you are looping in a shell, `$?` finally means what it looks like.

### The bridge must be https (since v0.15.0)

`bridge configure --url` refuses anything but `https://`, and the client no
longer follows redirects: `urllib` keeps the `Authorization` header across one,
including to another host. A redirecting bridge is now an error rather than a
silent hop. Pass the token with `--token-stdin` for the same reason as the
passwords below.

### `connect` may report an accepted host key

On a first contact it prints the key it accepted and adds `host_key_accepted` to
the JSON. That is information, not a failure — nothing is blocked. It appears
only the first time a machine talks to that host.

### Passing a password: use `--password-stdin`

Five commands take a password. Each accepts it two ways, and **an agent should
always use the second**:

```bash
# Readable by every other user of this machine and of the server
contao-ai-cli user password --username alice --password "Geheim"

# Not in any process list
printf '%s\n' "Geheim" | contao-ai-cli user password --username alice --password-stdin
```

The same applies to `user create --password-stdin`,
`security hash-password --password-stdin` (whose `PASSWORD` argument became
optional in v0.14.0 for this reason), and since v0.27.0 to the two member commands
below. One line is read; only the trailing newline is stripped, so a password may
begin or end with a space.

### Front end members: `member create` and `member password` (v0.27.0, core-bundle v0.26.0)

```bash
printf '%s\n' "Geheim-123" | contao-ai-cli --json member create --username anna \
  --firstname Anna --lastname Muster --email anna@example.org --password-stdin --set groups=2
printf '%s\n' "Neu-456" | contao-ai-cli --json member password --username anna --password-stdin
contao-ai-cli --json member update anna --set email=anna@example.com
contao-ai-cli --json member delete anna --yes   # recoverable via undo
```

`member update` and `member delete` take the username as a **positional argument**, not
`--username` like `create` and `password`. `member delete` asks on a terminal like every
record delete (v0.29.0); `--yes` skips the question.

- **Until v0.27.0 `member create` never worked**: the server command it called did not
  exist. Both need core-bundle v0.26.0; an older one answers that the command is not
  available and names `bundle update core`.
- **The password reaches the server only on stdin**, even when given as `--password`
  here: the server commands have no password option at all.
- Checked as Contao's password field does: at least `minPasswordLength` characters (8 by
  default), not the username. Hashed with the hasher Contao's front end login uses. `tl_member.password`'s
  save callbacks run, so the `setNewPassword` hook fires as in the back end.
- `member create` sets `login` (the member may log in) and `dateAdded`. `username` and
  `email` must be unique, `email` valid. `--set` takes what `member update` takes
  (`groups=1,2`, `disable`, `start`, address fields), minus `username`, which belongs to
  `--username`; `password` is refused there too.
- **`member update` refuses `password`** — use `member password`. It takes `--set` like
  every other update command; `--field`, its own spelling until v0.27.0, still works.
- **Fields of other bundles work here too** (core-bundle v1.1.0). `member update`,
  `member create` and `user update` refuse only credentials and authentication state —
  `password`, `secret`, `useTwoFactor`, `backupCodes`, `trustedTokenVersion`, `session`;
  for `user` also `admin`, `pwChange` and `amg` (the allowed member groups — the front-end
  preview authenticates **as** them, so it is impersonation); for `member create` also
  `username`, which belongs to `--username`. Everything else is checked against the table's
  real columns, so a column another bundle adds to `tl_member` is writable:
  `--set consho_vatId=ATU…`. The comparison ignores case, so `--set Password=…` is refused
  as well.
  **With core-bundle 1.0.0 or older the same call answers *"Field(s) not allowed"*** —
  those versions carried a hand-maintained allow list of Contao's own fields
  (core-bundle Issue #71). Ask `dca schema tl_member` which fields the table really has.
- **`--set id=…` is refused on every table** (core-bundle v1.1.0). Up to v1.0.0 it
  renumbered the record: the row moved to the new id while the answer still reported the
  old one, the version history stayed behind, and on `tl_user` it moved page ownership
  between accounts. `tstamp` is refused too — the write sets it itself, so passing it was
  reported as written and never was. **If an installation still runs core-bundle ≤ 1.0.0,
  never pass `id` in `--set`** (core-bundle Issue #72).
- The answer never contains the password or its hash. Each call is versioned and logged.

A command line is not private. On Linux `/proc/<pid>/cmdline` is world-readable
and on Windows any process can be enumerated the same way — so `--password` is
visible to anyone logged in, on **both** ends of the connection. Contao says so
itself: `contao:user:password` documents its own `--password` as *"not
recommended for security reasons"*.

`--password` still works and is not deprecated — piping is not always possible.
But when you are choosing, choose stdin.

A `printf` typed into an interactive shell still lands in that shell's **history**. Out of
a process list is not out of every record: read it into a variable first (`read -rs PW`)
or start the line with a space where `HISTCONTROL=ignorespace` is set.

### What `user create` does under the hood

Since v0.14.0 it makes **two** server calls: it creates the account with a random
throwaway secret, then sets the requested password through the prompt. This is
not decoration — `contao:user:create` cannot be driven through its prompts,
because it ends with a mandatory group question whose options are the groups of
that particular site, and `--no-interaction` suppresses the password prompt along
with everything else.

Consequence for a caller: if the second step fails, the command **raises** rather
than reporting `created`, and the account then exists with a password nobody
holds. The error says so and names the two ways out.
