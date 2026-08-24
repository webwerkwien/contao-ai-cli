# Changelog

All notable changes to this project are documented here. The project adheres to [Semantic Versioning](https://semver.org/) (within the pre-1.0 reservations).

This file was reconstructed from the git history and the GitHub releases on 2026-08-24, so entries before that date describe what the tags contain rather than what was written at release time.

## v0.4.3 — 2026-08-24

### Fixed

- **The CLI self-update never updated anything** ([#2](https://github.com/webwerkwien/contao-ai-cli/issues/2)). `connect` ran `pipx upgrade contao-ai-cli` and then printed `[OK] Update installed` unconditionally. `pipx upgrade` re-resolves the spec recorded at install time — and `pipx install git+…@v0.4.1` records that tag, which resolves to the same version forever. The flow detected the update, asked, ran a no-op, and reported success. `install_cli_update()` now forces a reinstall at the requested tag (`pipx install --force git+…@vX.Y.Z`), which is immune to whatever spec the existing installation carries.
- The result is read back from `pipx list --json` instead of assumed. Success is reported only when the version actually moved; otherwise the flow names the version it is still on and prints the manual command. A missing or hanging `pipx` is handled rather than raised into the middle of `connect`.

### Notes

The bug had been in place since v0.1.1 and survived every release because `check_cli_update()` only enters that branch when an update is genuinely pending — it was unreachable except in the one moment it mattered.

## v0.4.2 — 2026-08-24

### Changed

- **`connect` no longer writes `allow-plugins` into the project `composer.json` on a Managed Edition** ([#1](https://github.com/webwerkwien/contao-ai-cli/issues/1)). That freedom deliberately lives in `contao-manager/config.json`, which the Contao Manager uses as its own `COMPOSER_HOME`; the CLI was undoing that separation on production sites, unasked, and putting a second writer on a file the manager already manages. Install and update now go through the manager's Composer passthrough (`php public/contao-manager.phar.php composer require|update`), which brings its own `allow-plugins` along.
- Installations without a Contao Manager still fall back to plain `composer`, but ask before writing to `composer.json` — naming only the plugins that are not already allowed — and report the file as modified afterwards.
- Both core-bundle prompts default to **no**. They write to the project's `composer.json`, and the previous `default=True` meant a single Enter was enough.

### Added

- `detect_contao_manager()` — one SSH probe for the phar (`public/`, or the `web/` that installations carried over from Contao 4 still use), the `contao-manager/` config directory, and `contao/manager-bundle` in the `composer.lock`. The phar plus the config directory decides; `manager-bundle` corroborates but cannot stand alone, since without a phar there is nothing to call.

### Fixed

- `get_core_bundle_installed_version()` called a hardcoded `php` instead of the session's `php_path`. On a host that needs `/opt/php-X.Y/bin/php` the check returned `None`, and `connect` then offered to install a bundle that was already there.
- The `→` in both update messages is not encodable in cp1252, so `click.echo` raised and the update branch died before its prompt ever appeared. This bites whenever `sys.stdout.encoding` resolves to cp1252 — that is, when no console at code page 65001 is attached: piped output under Git Bash, CI, cron, or an agent harness capturing stdout. A Windows terminal already running at 65001 resolves to UTF-8 and is unaffected, which is why the branch could stay broken unnoticed.
- This is the fourth cp1252 casualty in this project — a separator in v0.3.0, an arrow in v0.3.1, a tip line in v0.3.2 — and each was fixed by spotting one more symbol. A regression test now walks the AST of `cli_connect.py` and asserts every string literal encodes, instead of relying on catching the next one by eye.

## v0.4.1 — 2026-05-09

### Fixed

- `test_file_write` still asserted the old `/tmp/contao_write_*` upload path while the production code had long been uploading to `<contao_root>/var/bridge-uploads/`. Test-only change, no behaviour difference.

## v0.4.0 — 2026-05-09

### Changed

- **Package layout flattened**: `contao/agent-harness/cli_anything/contao/` becomes `contao_ai_cli/` at the repository root, and imports move from `cli_anything.contao.*` to `contao_ai_cli.*`. The inner `setup.py` and a stale inner `README.md` are gone. `cli_anything` was a multi-CMS harness concept that never got a second implementation, so the double `contao/` nesting was purely historical sediment.

Reinstall rather than upgrade:

```bash
pipx install --force git+https://github.com/webwerkwien/contao-ai-cli.git@v0.4.0
```

## v0.3.4 — 2026-05-09

### Fixed

- Defence in depth after v0.3.3: `encoding="utf-8"` pinned on all session JSON I/O and on the E2E subprocess calls, not just the three SSH paths. Also forward-compatible with PEP 686, which makes UTF-8 mode the default from Python 3.15.

## v0.3.3 — 2026-05-09

### Fixed

- **Silent data corruption in every list command.** `subprocess.run(text=True)` without `encoding=` uses the Windows locale default (cp1252), so the UTF-8 bytes of an umlaut arrived as two Latin-1 characters (`\xc3\xa4` → `Ã¤`). The row then ran one character longer than Symfony's separator line, every column right of the umlaut shifted left, and the last character of each cell was cut off. No crash, just wrong values — `event`, `news`, `page`, `member` and the rest were all affected. Fixed with `encoding="utf-8", errors="replace"` in `run`, `run_raw` and `scp_upload`; Symfony Console always writes UTF-8 regardless of the host locale.

Found during a bridge test against the live server, where a cloned record came back as *„Jährliche Konferen"*.

### Changed

- README rewritten in English only, with a consistent ecosystem table and a `bridge` section; the beta disclaimer now says what may shift.

## v0.3.2 — 2026-05-08

### Fixed

- `--session` accepts a bare session name (`--session c5-axeltest`), not just a full path.
- The closing tip line in `health` is ASCII-only — another cp1252 casualty on the Windows console.

## v0.3.1 — 2026-05-08

### Fixed

- Replaced the Unicode arrow in `health`'s "update available" branch with ASCII, which crashed under a Windows cp1252 console. Same root cause as the separator fix in v0.3.0 — one more symbol that had slipped through.

## v0.3.0 — 2026-05-08

### Added

- **`health`** — a read-only status check for all three components without forcing a reconnect: the installed CLI version against the latest GitHub release, `contao-ai-core-bundle` on the connected server against the latest stable on Packagist, and the configured bridge URL with a masked token. Until now these checks only ran on `connect`, so a long-running session never noticed a core-bundle update. Supports `--json` for agent consumption as well as text output.

## v0.2.0 — 2026-05-08

### Added

- **`bridge` command group** (Phase 10.3) — calls the `contao-ai-backend-bundle` macro tools (`record_clone`, `record_rewrite`) over HTTPS instead of orchestrating CRUD over SSH and the console. Intended for bulk LLM jobs ("translate every news item in archive 5"), atomic container clones of a news archive, calendar, FAQ category or page tree, and generally anything where the agent would otherwise emit ten or more console calls in a row.
- `user update` accepts `--set` as an alias for `--field`.

## v0.1.1 — 2026-04-26

### Fixed

- `allow-plugins` is set before `composer require`/`update`, for Composer 2.2+ compatibility. (This is the write that v0.4.2 removed again for Managed Editions.)
- Self-update switched from `pip install --upgrade` to `pipx upgrade`. (This is the call that v0.4.3 replaced, having turned out to be a no-op on a tag-pinned installation.)
- `setup.py` added at the repository root so `pipx`/`pip` can install the package at all.
- Corrected the PHP escaping in the core-bundle version check, and skip the update check for `dev-*` versions instead of reporting a false positive.

### Added

- The CLI self-update check and the core-bundle install/update flow in `connect`.
- `CLAUDE.md` agent guide. Leaked credentials removed from the internal docs.

### Changed

- Installation instructions moved from `pip` to `pipx`, which places the scripts directory on `PATH` reliably on Windows where `pip` does not.

## v0.1.0 — 2026-04-24

First public release, MIT-licensed, as `contao-ai-cli` (previously `contao-cli-agent`, and before that `cli-anything-contao`).

### Added

- SSH backend wrapping `php bin/console` on a remote Contao 5 installation, with named sessions in `~/.contao-ai-cli/`.
- Command groups covering the Contao console surface: `page`, `article`, `content`, `news`, `event`, `faq`, `member`, `user`, `file`, `folder`, `template`, `comment`, `version`, `search`, `schema`, `backup`, `cache`, `layout`, `listing`, `form`, `mailer`, `messenger`, `newsletter`, `security`, `debug`.
- DCA-driven schema support: dynamic table discovery from the server cache, mandatory-field information fetched from the live server, field validation on create, and `schema resolve` for `__callback__` option lists.
- `table_parser` for turning Symfony Console table output into structured data.
- Detection of `contao-ai-core-bundle` on the target server, which gates the full CRUD commands, plus an offer to install it during `connect`.
