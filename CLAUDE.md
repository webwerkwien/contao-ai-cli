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

## Error handling

- All commands exit with code `0` on success, non-zero on failure
- With `--json`, errors are returned as `{"error": "..."}` objects
- SSH timeouts default to 60s; composer operations use 180s internally

## Security notes

- Session files contain SSH connection details — treat them as credentials
- The CLI never stores passwords; use SSH key authentication
- Always maintain a current backup of the Contao installation before making changes
