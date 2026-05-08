# contao-ai-cli

Agent-native Python CLI for managing Contao 5 installations from the terminal — over SSH for CRUD, over HTTPS for bulk LLM macros. Designed to be used directly or handed to an AI agent (e.g. Claude Code) as a tool set.

> **Beta software.** CLI commands and session formats may change without notice. Use at your own risk. Always maintain a current backup of your Contao installation before use.

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
| `bridge` | Call backend macro tools (record_clone, record_rewrite) over HTTPS — see below |
| `health` | Show CLI / core-bundle / bridge update status (read-only) |

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

`contao-ai-cli health` shows CLI / core-bundle / bridge update status without requiring a re-connect.

## License

MIT — see [LICENSE](LICENSE).

This software is provided "as is", without warranty of any kind. The authors accept no liability for any damages arising from its use. Always back up your data before use.
