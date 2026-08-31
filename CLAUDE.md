# contao-ai-cli — Claude Agent Guide

This is an agent-native CLI for managing Contao 5 installations via SSH.
It wraps Contao's Symfony Console (`php bin/console`) and provides structured
output suitable for AI-driven workflows.

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
  `true` and would be stored as `1`. Setting a field outright is safe —
  `--set stunden=2` passes a string and never meets the cast.
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

## Available command groups

`article`, `backup`, `bridge`, `cache`, `comment`, `contao`, `content`, `debug`, `event`, `faq`, `file`, `form`, `layout`, `listing`, `mailer`, `member`, `member-group`, `messenger`, `news`, `newsletter`, `page`, `record`, `schema`, `search`, `security`, `settings`, `template`, `undo`, `user`, `user-group`, `version`

Standalone commands: `connect`, `health`, `repl`, `session-delete`, `session-list`

Run `contao-ai-cli <group> --help` for the subcommands of a group; the full table is in
[README.md](README.md) and is generated from the command tree, so it cannot go stale.

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

## Security notes

- Session files contain SSH connection details — treat them as credentials
- The CLI never stores passwords; use SSH key authentication
- Always maintain a current backup of the Contao installation before making changes
