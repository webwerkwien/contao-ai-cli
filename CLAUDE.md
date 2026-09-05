# contao-ai-cli — Claude Agent Guide

This is an agent-native CLI for managing Contao 5 installations via SSH.
It wraps Contao's Symfony Console (`php bin/console`) and provides structured
output suitable for AI-driven workflows.

**Everything below Step 1 describes how to *use* this CLI against a site.** If
you are working *on* the CLI itself, read the next section first.

---

## Working on this CLI

```bash
python -m pytest -q        # the gate — must be green
```

There is no linter and no type checker configured; the suite is the whole gate.

Healthy output has this shape:

```
… passed, … skipped in …s
```

The counts are deliberately not written down — they change with every commit.
What must hold is that nothing failed.

**Run it before reporting any task complete, and paste the output.**

**For a bug fix, write the failing test first.** Reproduce the bug as a test, run
it, confirm it fails for the reason you expect, and commit that test before
touching the implementation. Do not edit test files while making the fix — a test
that existed before the fix, and could not be rewritten, is the proof.

### Two things that go wrong here

**1. This file is part of the product, and it drifts.**

`test_docs_match_cli.py` pins README and this guide to the real command tree —
name, existence, option spelling — because both once promised commands that did
not exist. **Its own docstring names its boundary:** it does not check what a
command *answers*. On 2026-09-01 `ext run` changed its return value and then
gained a `hint` field; the file stayed green both times while this guide said
nothing about either.

> A green `docs match cli` is a statement about the command tree only. If what a
> caller sees has changed, no test covers it — that is a release-round step in
> the `contao-ai-status` skill.

**2. A measurement belongs to the binary and the environment it was taken in.**

On Windows the code picks `C:\Windows\System32\OpenSSH\ssh.exe` explicitly. A
reproduction typed into Git Bash runs MSYS-ssh instead and answers differently —
close enough to look like a result, different enough to be the wrong one. Drive
the real code path (`ContaoBackend.__new__` plus `_ssh_args()`) and set the same
environment the code sets.

### Convention

Every scanning test needs a counter and at least one known non-match. A search
that finds nothing passes exactly like one that finds everything.

---

## Step 1: Check for existing sessions

```bash
contao-ai-cli session-list
```

If a session exists, you can start using commands immediately.
Session files are stored in `~/.contao-ai-cli/<name>.json`.

## Step 2: Connect (first time only)

```bash
contao-ai-cli connect \
  --host your-server.example.com \   # hostname or IP of your web server
  --user ssh-username \              # SSH login user
  --root /path/to/contao \          # absolute path to the Contao root on the server
  --key ~/.ssh/id_ed25519 \         # path to your SSH private key (adjust if different)
  --name my-site                    # local session name (your choice)
```

The connect command is interactive — it will prompt for confirmation at several points:
1. A warning that data can be irreversibly modified → confirm to proceed
2. Offer to create a database backup → recommended: confirm
3. Check for CLI updates → confirm to install if available
4. Check whether contao-ai-core-bundle is installed → confirm to install/update if needed
   (defaults to **no**, because installing writes to the project's `composer.json`)

On a **Managed Edition** the install/update runs through the Contao Manager's Composer
passthrough (`php public/contao-manager.phar.php composer …`), which uses the manager's
own `allow-plugins` config — the project `composer.json` config block is left untouched.
Only installations without a Contao Manager fall back to plain `composer`, and that path
asks separately before writing `allow-plugins` into `composer.json`.

> ⚠️ `connect` requires a human operator. Do not attempt to run it autonomously.
> For automated workflows, use an existing session (`session-list`) instead.

> ⚠️ Never hardcode real hostnames, usernames, passwords, or key paths
> in any committed file. Always ask the user for connection details.

## Step 3: Use JSON output for machine-readable results

Always use `--json` when processing output programmatically:

```bash
contao-ai-cli --json page list
contao-ai-cli --json news list
contao-ai-cli --json user list
contao-ai-cli --json backup list
```

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
contao-ai-cli --json content list --article 1

# Create
contao-ai-cli --json page create --title "New Page" --pid 1 --type regular

# Update — repeat --set for each field
contao-ai-cli --json content update 5 --set headline="New Title"
contao-ai-cli --json page update 1 --set title="Home" --set robots=noindex

# Publish / unpublish
contao-ai-cli --json page publish 1
contao-ai-cli --json comment publish 7 --unpublish
```

> Deleting cascades to child records — a page takes its subpages, articles and content
> elements with it. The whole set lands in one `tl_undo` entry, so it stays recoverable
> from the back end's *Restore* module. On a terminal the CLI asks first, the same as the
> Contao back end does; `--yes` skips the prompt for non-interactive use.

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

⚠️ `form list` and `form fields` predate this and still parse Symfony's ASCII table out of
`doctrine:query:sql`; everything above answers with JSON. Use `form read` / `form field-read`
when you want structured output.

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
the parent, the children and their links back in one step.

### Cache and maintenance

```bash
contao-ai-cli cache clear
contao-ai-cli cache warmup
```

### Backup

```bash
contao-ai-cli backup create
contao-ai-cli --json backup list
```

### Schema inspection (requires contao-ai-core-bundle)

```bash
contao-ai-cli --json schema show tl_content
contao-ai-cli --json schema mandatory tl_news
contao-ai-cli --json schema resolve tl_content type
```

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

Unit fields (`width`, `headerHeight`, `footerHeight`, `widthLeft`,
`widthRight`): a plain number keeps the record's existing unit, `--set
<field>_unit=vw` changes it.

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
  character count shifted the columns silently. That happened: on 2026-05-09 a UTF-8
  umlaut truncated a value and the command still reported success.
- **A truncated listing says so.** `count` against `total`. The server caps at 100 rows,
  defaults to 20; pass `--limit`/`--offset`. A listing that is cut off is never silent
  about it.
- **Column names are checked against the DCA**, so a wrong one is refused by name rather
  than answering something plausible.

`--limit`/`--offset` exist on every listing. `file list --path` matches a path prefix
through `--filter-prefix`, bound as a parameter, so a `%` in the value stays literal.

**`page tree` is its own command** (`contao:page:tree`): the tree is built server-side,
level by level, because `record:list` caps at 100 rows and a real site passes that —
wienerwandern.at has 283 pages. Two levels by default; `truncated` says whether pages
exist below the cut, so a depth-limited tree cannot be mistaken for a complete one. Use
`--root` to descend into one branch, `--depth` for more levels.

**One exception, on purpose:** `listing data` still writes its own SQL. `list_where` is a
free SQL fragment stored in the listing module, so the query is configured in the site
rather than by the caller — it cannot be expressed as checked equality filters, and
ignoring it would answer with different rows than the module shows in the front end.

⚠️ **All listings now need contao-ai-core-bundle on the target.** They used to run through
`doctrine:query:sql`, which is plain Contao.

## Available command groups

`article`, `backup`, `bridge`, `cache`, `comment`, `contao`, `content`, `debug`, `event`, `faq`, `file`, `form`, `layout`, `listing`, `mailer`, `member`, `member-group`, `messenger`, `news`, `newsletter`, `page`, `record`, `schema`, `search`, `security`, `settings`, `template`, `undo`, `user`, `user-group`, `version`

Standalone commands: `connect`, `health`, `repl`, `session-delete`, `session-list`

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

**`ext run` starts commands under `contao:` only.** Everything else — the
framework's own namespace, and a site bundle that registered its command
elsewhere — is listed under `out_of_reach` and can be described, but not run.
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
says so — the wrapped commands' guarantees still do not apply. Three things are worth
treating differently:

- **`IRREVERSIBLE`** is the line to stop at. A database write has `tl_undo`; this has
  nothing, and no part of this CLI can take it back.
- **`hands off`** is the extension saying a generic writer must not touch that table,
  usually because its transitions hang on DCA callbacks. It holds for a future dedicated
  wrapper too, not only for a generic path.
- **The retention** beside a trail is read from the installation, not declared. `tl_log`
  and `tl_version` are 7 days against 90, so "leaves a log entry" and "leaves a version"
  are not interchangeable assurances.

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
# The CLI loads the default session automatically (first available)
```

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

**Version snapshots (`tl_version`)** are the durable trace, for the ten tables the
core bundle covers (`tl_page`, `tl_article`, `tl_content`, `tl_news`, `tl_calendar_events`,
`tl_faq`, `tl_files`, `tl_layout`, `tl_member`, `tl_user`). Deletions additionally land
in `tl_undo` and stay restorable from the back end's *Restore* module.

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

- All commands exit with code `0` on success, non-zero on failure
- With `--json`, errors are returned as `{"error": "..."}` objects
- SSH timeouts default to 60s; composer operations use 180s internally

### Error reports (since v0.16.0) — and what you must not do with them

When something fails **unexpectedly**, the CLI writes a report to stderr under
the usual `Error: …` line, headed `## Fehlerbericht contao-ai`. It contains
versions, the exception class, our own file and line, and the (masked) message.
Exit code and stdout are unchanged, so nothing about parsing output changes.

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
*answers*, and they get no report. If you see one, something is genuinely broken
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

Three commands take a password. Each accepts it two ways, and **an agent should
always use the second**:

```bash
# Readable by every other user of this machine and of the server
contao-ai-cli user password --username alice --password "Geheim"

# Not in any process list
printf '%s\n' "Geheim" | contao-ai-cli user password --username alice --password-stdin
```

The same applies to `user create --password-stdin` and
`security hash-password --password-stdin` (whose `PASSWORD` argument became
optional in v0.14.0 for this reason). One line is read; only the trailing newline
is stripped, so a password may begin or end with a space.

A command line is not private. On Linux `/proc/<pid>/cmdline` is world-readable
and on Windows any process can be enumerated the same way — so `--password` is
visible to anyone logged in, on **both** ends of the connection. Contao says so
itself: `contao:user:password` documents its own `--password` as *"not
recommended for security reasons"*.

`--password` still works and is not deprecated — piping is not always possible.
But when you are choosing, choose stdin.

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
