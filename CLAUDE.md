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
  --host your-server.example.com \
  --user ssh-username \
  --root /var/www/contao \
  --key ~/.ssh/id_ed25519 \
  --name my-site
```

The connect command will:
- Test the SSH connection
- Offer to create a database backup
- Check for CLI updates
- Check whether contao-ai-core-bundle is installed (and offer to install/update it)

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
# Read
contao-ai-cli --json page list
contao-ai-cli --json page read --id 1
contao-ai-cli --json article list --pid 1
contao-ai-cli --json content list --pid 1

# Create / Update / Delete
contao-ai-cli --json page create --title "New Page" --pid 1 --type regular
contao-ai-cli --json content update --id 5 --set headline="New Title"
contao-ai-cli --json news delete --id 3
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
contao-ai-cli --json schema dca --table tl_content
contao-ai-cli --json schema module --type news_list
```

## Available command groups

`page`, `article`, `content`, `news`, `event`, `faq`, `member`, `user`,
`file`, `folder`, `template`, `comment`, `version`, `search`, `schema`,
`backup`, `cache`, `layout`, `listing`, `form`, `mailer`, `messenger`,
`newsletter`, `security`, `debug`

Full CRUD support requires [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle)
to be installed on the target Contao site.

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
