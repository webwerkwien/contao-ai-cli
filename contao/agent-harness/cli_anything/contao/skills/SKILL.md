---
name: cli-anything-contao
description: Agent-native CLI for Contao 5 CMS via SSH. Wraps Contao's Symfony Console (php bin/console) with a Python CLI that AI agents can use remotely. Supports cache management, migrations, user management, backups, maintenance mode, debug tools, and message queue operations.
---

# cli-anything-contao

Agent-native CLI for Contao 5 via SSH. The real Contao installation is a hard dependency.

## Prerequisites

- Python 3.10+
- SSH access to a Contao 5 installation
- `click`, `prompt_toolkit` Python packages
- **Windows / Git Bash**: Prefix commands with `MSYS_NO_PATHCONV=1` to prevent Unix path conversion

## Installation

```bash
cd contao/agent-harness
pip install -e .
```

## Setup

```bash
# Connect to a Contao installation
cli-anything-contao connect \
  --host c5.axeltest.at \
  --user c155929_C5 \
  --root /var/www/clients/client1/web246/web

# Named sessions (multiple installations)
cli-anything-contao connect --host staging.example.com --user deploy --root /var/www --name staging
```

## Command Groups

| Group | Commands | Description |
|---|---|---|
| `connect` | — | Connect to Contao installation, save session |
| `cache` | `clear`, `warmup`, `pool-list`, `pool-clear` | Cache management |
| `contao` | `migrate`, `install`, `symlinks`, `filesync`, `cron`, `cron-list`, `maintenance`, `resize-images` | Contao core operations |
| `user` | `list`, `create`, `password` | Backend user management |
| `backup` | `create`, `list`, `restore` | Database backup management |
| `debug` | `twig`, `dca`, `pages`, `plugins`, `router` | Debug and inspection |
| `messenger` | `stats`, `failed`, `retry` | Message queue operations |
| `repl` | — | Interactive REPL mode |

## Usage Examples

```bash
# Connect once, then use all commands
cli-anything-contao connect --host mysite.at --user deploy --root /var/www/contao

# Cache
cli-anything-contao cache clear
cli-anything-contao cache warmup

# Migrations
cli-anything-contao contao migrate --dry-run
cli-anything-contao contao migrate

# Maintenance mode
cli-anything-contao contao maintenance enable
cli-anything-contao contao maintenance status
cli-anything-contao contao maintenance disable

# Users
cli-anything-contao user list
cli-anything-contao user create --username admin2 --password secret --admin

# Backups
cli-anything-contao backup create
cli-anything-contao backup list
cli-anything-contao backup restore backup__20260418051812.sql.gz

# Debug
cli-anything-contao debug dca tl_content
cli-anything-contao debug twig
cli-anything-contao debug pages

# Message queue
cli-anything-contao messenger stats
cli-anything-contao messenger failed
```

## JSON Output (for agents)

All commands support `--json` for machine-readable output:

```bash
cli-anything-contao --json user list
cli-anything-contao --json backup list
cli-anything-contao --json contao maintenance status
```

## Deployment Workflow

```bash
cli-anything-contao contao maintenance enable
cli-anything-contao contao migrate
cli-anything-contao cache clear
cli-anything-contao contao filesync
cli-anything-contao contao maintenance disable
```

## Multiple Sessions

```bash
# Save named sessions
cli-anything-contao connect --host prod.example.com --user deploy --root /var/www --name prod
cli-anything-contao connect --host staging.example.com --user deploy --root /var/www --name staging

# Use specific session
cli-anything-contao --session ~/.cli-anything-contao/prod.json cache clear
cli-anything-contao --session ~/.cli-anything-contao/staging.json contao migrate
```
