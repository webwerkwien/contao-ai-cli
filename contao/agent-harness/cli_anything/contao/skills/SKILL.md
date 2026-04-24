---
name: contao-ai-cli
description: Agent-native CLI for Contao 5 CMS via SSH. Wraps Contao's Symfony Console (php bin/console) with a Python CLI that AI agents can use remotely. Supports full CRUD for pages, articles, content elements, news, events, users, files, templates, and more — as well as cache management, backups, and debug tools.
---

# contao-ai-cli

Agent-native CLI for Contao 5 via SSH. Requires a running Contao 5 installation.
Full CRUD support requires [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle)
to be installed on the target site.

## Prerequisites

- Python 3.10+
- SSH access to a Contao 5 installation (key-based authentication recommended)
- `click`, `prompt_toolkit` Python packages
- **Windows / Git Bash**: Prefix commands with `MSYS_NO_PATHCONV=1` to prevent Unix path conversion

## Installation

```bash
pip install pipx
pipx ensurepath
pipx install git+https://github.com/webwerkwien/contao-ai-cli.git
```

## Setup

```bash
# Connect to a Contao installation (asks for confirmation + creates backup)
contao-ai-cli connect \
  --host your-server.example.com \
  --user ssh-username \
  --root /var/www/contao \
  --key ~/.ssh/id_ed25519 \
  --name my-site

# List saved sessions
contao-ai-cli session-list
```

> ⚠️ Never hardcode real hostnames, usernames, or key paths in any file.
> Connection details are provided by the user and stored in session files.

## Command Groups

| Group | Description |
|---|---|
| `page` | Read, create, update, delete, publish pages |
| `article` | Manage articles |
| `content` | Manage content elements |
| `news` | Manage news entries |
| `event` | Manage calendar events |
| `faq` | Manage FAQ entries |
| `member` | Manage frontend members |
| `user` | Manage backend users |
| `file` | Read, write, and manage files |
| `folder` | Create folders |
| `template` | List, read, and write templates |
| `comment` | Manage comments |
| `version` | List, read, create, and restore versions |
| `search` | Search the fulltext index |
| `schema` | Inspect DCA field definitions and module config |
| `backup` | Create and restore database backups |
| `cache` | Clear and warm up the Symfony cache |
| `layout` | Read layout configurations |
| `listing` | Read listing module configurations |
| `form` | Read form definitions |
| `mailer` | Inspect mailer configuration |
| `messenger` | Inspect messenger configuration |
| `newsletter` | Manage newsletters |
| `security` | Inspect security configuration |
| `debug` | Debug utilities |

## JSON Output (for agents)

Always use `--json` for machine-readable output:

```bash
contao-ai-cli --json page list
contao-ai-cli --json user list
contao-ai-cli --json backup list
contao-ai-cli --json news list --pid 3
```

## Usage Examples

```bash
# Cache
contao-ai-cli cache clear
contao-ai-cli cache warmup

# Pages
contao-ai-cli --json page list
contao-ai-cli --json page read --id 1
contao-ai-cli --json page create --title "New Page" --pid 1 --type regular

# Content
contao-ai-cli --json content list --pid 5
contao-ai-cli --json content update --id 12 --set headline="Updated"

# Users
contao-ai-cli --json user list
contao-ai-cli --json user create --username editor --name "Max Mustermann" --email max@example.com

# Backups
contao-ai-cli backup create
contao-ai-cli --json backup list

# Schema inspection
contao-ai-cli --json schema dca --table tl_content
contao-ai-cli --json schema module --type news_list

# Search
contao-ai-cli --json search query --q "keyword"
```

## Multiple Sessions

```bash
# Save named sessions for multiple installations
contao-ai-cli connect --host prod.example.com --user deploy --root /var/www --name prod
contao-ai-cli connect --host staging.example.com --user deploy --root /var/www --name staging

# Session files: ~/.contao-ai-cli/<name>.json
```

## Deployment Workflow

```bash
contao-ai-cli backup create
contao-ai-cli cache clear
contao-ai-cli cache warmup
```
