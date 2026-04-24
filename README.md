# contao-ai-cli

> ⚠️ **Beta Software / Beta-Software**
> This tool is under active development. CLI commands and session formats may change without notice. Use at your own risk. Always maintain a current backup of your Contao installation before use.
>
> Dieses Tool befindet sich in aktiver Entwicklung. CLI-Befehle und Session-Formate können sich ohne Vorankündigung ändern. Nutzung auf eigene Gefahr. Vor dem Einsatz stets ein aktuelles Backup der Contao-Installation anlegen.

---

## The contao-ai ecosystem / Das contao-ai-Ökosystem

This package is part of the **contao-ai** family — a set of tools for AI-assisted Contao 5 management.

Dieses Paket ist Teil der **contao-ai**-Familie — einer Sammlung von Werkzeugen für die KI-gestützte Verwaltung von Contao 5.

| Package | What it is / Was es ist | When to use / Wann verwenden |
|---|---|---|
| [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) | Contao bundle — exposes CMS operations as Symfony console commands / Contao-Bundle — stellt CMS-Operationen als Symfony-Console-Commands bereit | Required as the foundation layer. Install on any Contao site you want to manage via AI. / Wird als Grundlage benötigt. Auf jeder Contao-Seite installieren, die KI-gesteuert verwaltet werden soll. |
| **contao-ai-cli** *(this package)* | Python CLI — connects to Contao via SSH and runs commands / Python-CLI — verbindet sich via SSH mit Contao und führt Commands aus | For developers and agencies: manage Contao from the terminal or hand control to an AI agent. / Für Entwickler und Agenturen: Contao vom Terminal aus verwalten oder die Kontrolle an einen KI-Agenten übergeben. |
| contao-ai-backend-bundle *(planned / geplant)* | Contao backend module — browser-based AI chat interface with support for multiple AI providers (Anthropic Claude, OpenAI, and more) / Contao-Backend-Modul — browser-basierte KI-Chat-Oberfläche mit Unterstützung für mehrere KI-Anbieter (Anthropic Claude, OpenAI u.a.) | For end users and editors: use AI directly inside the Contao backend, no SSH or terminal needed. / Für Redakteure und Endnutzer: KI direkt im Contao-Backend nutzen, ohne SSH oder Terminal. |

---

## English

### What it does

contao-ai-cli is an agent-native command-line tool for managing Contao 5 installations via SSH. It works standalone for simple read operations, and unlocks full CRUD support when [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) is installed on the target site.

Designed to be used directly from the terminal or handed to an AI agent (e.g. Claude Code) as a tool set for autonomous CMS management.

### Requirements

- Python >= 3.10
- SSH access to your web host
- [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) installed on the Contao site (for full CRUD support)

### Installation

```bash
pip install git+https://github.com/webwerkwien/contao-ai-cli.git
```

### Quick Start

```bash
# Connect to a Contao installation and save the session
contao-ai-cli connect --host example.com --user deploy --root /var/www/html

# List saved sessions
contao-ai-cli session-list

# Start interactive mode
contao-ai-cli repl
```

### Available Command Groups

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

### License

MIT — see [LICENSE](LICENSE).

This software is provided "as is", without warranty of any kind. The authors accept no liability for any damages arising from its use. Always back up your data before use.

---

## Deutsch

### Was es macht

contao-ai-cli ist ein agenten-natives Kommandozeilenwerkzeug zur Verwaltung von Contao-5-Installationen via SSH. Es funktioniert eigenständig für einfache Leseoperationen und ermöglicht vollständige CRUD-Unterstützung, wenn [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) auf der Zielseite installiert ist.

Gedacht für den direkten Einsatz im Terminal oder als Werkzeugset für einen KI-Agenten (z.B. Claude Code) zur autonomen CMS-Verwaltung.

### Voraussetzungen

- Python >= 3.10
- SSH-Zugang zum Webhost
- [contao-ai-core-bundle](https://github.com/webwerkwien/contao-ai-core-bundle) auf der Contao-Seite installiert (für vollständige CRUD-Unterstützung)

### Installation

```bash
pip install git+https://github.com/webwerkwien/contao-ai-cli.git
```

### Schnellstart

```bash
# Mit einer Contao-Installation verbinden und Session speichern
contao-ai-cli connect --host example.com --user deploy --root /var/www/html

# Gespeicherte Sessions auflisten
contao-ai-cli session-list

# Interaktiven Modus starten
contao-ai-cli repl
```

### Verfügbare Befehlsgruppen

Siehe Tabelle im englischen Abschnitt.

### Lizenz

MIT — siehe [LICENSE](LICENSE).

Diese Software wird ohne jegliche Gewährleistung bereitgestellt. Die Autoren übernehmen keine Haftung für Schäden, die aus der Nutzung entstehen. Vor dem Einsatz stets Daten sichern.
