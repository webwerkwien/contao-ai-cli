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

## Available command groups

`article`, `backup`, `bridge`, `cache`, `comment`, `contao`, `content`, `debug`, `event`, `faq`, `file`, `form`, `layout`, `listing`, `mailer`, `member`, `messenger`, `news`, `newsletter`, `page`, `schema`, `search`, `security`, `template`, `user`, `version`

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
