# Changelog

All notable changes to this project are documented here. The project adheres to [Semantic Versioning](https://semver.org/) (within the pre-1.0 reservations).

This file was reconstructed from the git history and the GitHub releases on 2026-08-24, so entries before that date describe what the tags contain rather than what was written at release time.

## v0.8.5 - 2026-08-31

> **Needs core bundle v0.2.23.**

### Added

- **The form generator, write half.** The `form` group grows from two commands to eleven: `read`, `create`, `update`, `delete` for the form, and `field-types`, `field-read`, `field-create`, `field-update`, `field-delete` for its fields.

  ```bash
  contao-ai-cli --json form field-types
  contao-ai-cli --json form create --title "Contact" \
      --set sendViaEmail=1 --set recipient=info@example.com --set subject="New enquiry"
  contao-ai-cli --json form field-create --form 6 --type select \
      --set name=salutation --set label=Salutation --set "options=mrs=Mrs.|mr=Mr."
  contao-ai-cli --json form field-create --form 6 --type submit --set slabel=Send
  ```

  **Run `field-types` before creating a field.** 21 types, and each one requires something different — a `submit` needs `slabel`, a `select` needs `name` and `options`, a `captcha` needs nothing. Guessing means provoking an error.

  `recipient` and `subject` are required only once `--set sendViaEmail=1` opens that subpalette; a form that just stores its values needs neither.

  **`options` takes a short form** — `"mrs=Mrs.|mr=Mr."`, or `"red|green|blue"` when the label doubles as the value. It is the only invented shorthand in this CLI, and it exists because `select`, `radio` and `checkbox` are mandatory-options types: without it they could not be created at all.

  Fields are appended 128 apart. `form delete` removes every field with it — a form is one row, a form definition is usually a dozen — in one `tl_undo` entry.

### Note

- `form list` and `form fields` predate this and still parse Symfony's ASCII table out of `doctrine:query:sql`, while everything added here answers with JSON from the bundle. Migrating them onto `record:list` changes their output shape and is tracked separately; `form read` and `form field-read` give structured output in the meantime.

## v0.8.4 - 2026-08-31

> **Needs core bundle v0.2.22.**

### Added

- **The container a record lives in.** `news archive-*`, `event calendar-*` and `faq category-*` — read, create, update, delete for each.

  `news create`, `event create` and `faq create` have always taken a `--pid`, and the record that `pid` pointed at could not be created. **The child worked, the parent did not**, so the first news item on a fresh install still meant opening the back end.

  ```bash
  contao-ai-cli --json news archive-create --title "Blog" --set jumpTo=7
  contao-ai-cli --json event calendar-create --title "Touren" --set jumpTo=12
  contao-ai-cli --json faq category-create --title "Support" --set headline="FAQ"
  ```

  They sit **inside the existing groups**, next to the listings that were already there (`news archives`, `event calendars`, `faq categories`) — the same shape as `image-size item-*`. Those listings keep their names and their behaviour.

  Each takes `--title` and nothing else as a dedicated option. **What else is required comes from the DCA**, so the command reports it instead of the help text going stale: `jumpTo` for an archive or calendar, `groups` on top of that once `--set protected=1` opens its subpalette, and `headline` — not `jumpTo` — for an FAQ category.

  **Deleting a parent takes its children with it.** `archive-delete` also removes the entries and their content elements; the prompt names the child tables for that reason, the way `theme delete` does. One `tl_undo` entry for the whole set, so `undo restore` brings the parent, the children and their links back in one step — verified end to end on the test install.

## v0.8.3 - 2026-08-31

> **Needs core bundle v0.2.20.**

### Added

- **`undo` — the counterpart to `version restore`.** `list`, `read`, `restore`. `version restore` answers "this record changed and I want it back"; this one is for records that were **deleted**. Every delete this CLI triggers has written a `tl_undo` entry since core-bundle v0.2.8 — for a cascade, one entry covering the parent and everything under it — and nothing could read one back.

  ```bash
  contao-ai-cli --json undo list
  contao-ai-cli --json undo read 28
  contao-ai-cli --json undo restore 28 --yes
  ```

  **Read before restoring.** Records come back with their original IDs, which is what makes references from other tables valid again — and is also the one way it fails: if something has taken the ID since, the insert is refused and the entry stays. `read` reports that as `idsTaken`, and `droppedColumns` for columns the table has lost since, which come back missing rather than failing the restore.

  `list` leaves the `data` column out on purpose: it holds every restored row serialized, which is unreadable in a listing. That is what `read` decodes.

- **`settings` — global settings, which are not a table.** `read` and `update` for `tl_settings`, a `DC_File` whose values live in `system/config/localconfig.php`. This is why `record list tl_settings` answers "No readable columns" — correctly, since there is no schema to read.

  ```bash
  contao-ai-cli --json settings read
  contao-ai-cli --json settings update --set resultsPerPage=50 --yes
  ```

  `read` reports `value` and `persisted` separately: a setting can read `30` and be persisted `false`, meaning that is Contao's default and nobody chose it — it moves when the default moves.

  **The only write in this CLI that does not end in the database.** An unknown key is refused rather than written, because nothing would ever read it back or complain about it; a mandatory setting cannot be emptied; and the bundle reads the file back after saving to confirm the change actually landed.

### Changed

- `confirm_delete()` now sits on a general `confirm_action()`. `undo restore` and `settings update` are worth asking about but are not deletions, and "Delete …?" would have been the wrong question. Same rules either way — only on a terminal, `--yes` skips it.

## v0.8.2 - 2026-08-31

> **Update the core bundle to v0.2.19 as well.** It carries a fix that has nothing to do with permissions: the **create** commands were not converting the fields they stored. Of eleven that accept `--set`, four converted fileTree values and one converted multi-value fields — so `news create --set singleSRC=<uuid>` wrote a UUID as a string into a binary column, and `page create --set groups=1,2` wrote a bare string where Contao stores a list. Both reported success.

### Added

- **`user-group` — the permission table.** `list`, `read`, `create`, `update`, `delete`, `options`. `tl_user_group` decides what a back end editor can reach: modules, page and file mounts, editable fields, which tables they may create and delete in. Until now it was readable through `record list` and writable nowhere, so `user create` only ever produced an account that could do almost nothing.

  ```bash
  contao-ai-cli --json user-group options
  contao-ai-cli --json user-group options --table tl_news
  contao-ai-cli --json user-group create --name "Editors" \
      --set modules=page,article,files --set fop=f1,f2,f3 --set pagemounts=1
  contao-ai-cli --json user-group update 2 --set cud=tl_news::create,tl_news::update
  ```

  **`options` is not a convenience.** Everywhere else in this CLI a wrong value fails loudly against the DCA. Here it does not: a permission field accepts any string, stores it, and grants nothing. `--set modules=pages` (plural, wrong) reports success and leaves the group without page access, with no error anywhere to explain why. It is the one place in the tool where guessing does not self-correct, which is why the command exists and why `CLAUDE.md` says to run it first.

  **A permission field is replaced, not extended.** `--set modules=page` on a group that had five modules leaves it with one. That is how every multi-value field here behaves, but it costs more in this table than elsewhere.

- **`member-group` — the front end counterpart.** `list`, `read`, `create`, `update`, `delete` for `tl_member_group`, what a protected page, article or content element points at.

  ```bash
  contao-ai-cli --json member-group create --name "Members" --set redirect=1 --set jumpTo=7
  ```

  `jumpTo` is required only alongside `redirect=1` — it sits in a subpalette, and the bundle applies that rule from the DCA the same way the back end does. Without `jumpTo` the create is refused, with it accepted.

  Deleting either kind of group cascades to nothing, but Contao leaves the dead ID in `tl_user.groups` and in the `groups` field of protected content. Both confirmation prompts say so, because "nothing is deleted with it" and "nobody loses anything" are not the same sentence.

## v0.8.1 - 2026-08-31

### Fixed

- **The self-update check had been dead since v0.6.0, and said "up to date" the whole time.** It asked GitHub's `releases/latest`; `install_cli_update()` installs `git+…@v<x>`, a **tag**. Those two sources drifted: releases stopped being created after v0.5.2 while tags carried on to v0.8.0, so the check answered v0.5.2 for three versions running.

  Nothing looked wrong. `is_newer_version("0.5.2", "0.8.0")` is False, so `health` and `connect` printed "up to date" — the right words for a mechanism that had stopped working. A genuine update would have gone unmentioned in exactly the same way. Same shape as the v0.4.3 bug where `pipx upgrade` reported success for a no-op: a check that cannot fail visibly is a check nobody notices has failed.

  `check_cli_update()` now reads the tags endpoint — the same source the installer installs from, so the two cannot drift again. The list is reduced by version rather than taken from the top, because the endpoint promises no ordering; anything that is not a plain release version (`dev-main`, `1.0.0-beta`) drops out through `version_tuple()` on its own.

  The missing GitHub releases for v0.6.0 – v0.8.0 and core-bundle v0.2.15 – v0.2.18 have been created as well, so the release notes exist where people look for them.

## v0.8.0 - 2026-08-31

> **Update the core bundle to v0.2.18 as well.** It carries a fix that is not about the theme layer at all: a multi-value field (`--set groups=1`, `--set faq_categories=2`, any `eval.multiple` column) was written as a bare string where Contao stores a serialized array, and read back as nothing. Nothing failed and nothing was logged — the record simply had no value where it looked like it had one. Every entity was affected, not just the ones added here.

### Added

- **`image-size` — the theme layer's first group.** `list`, `read`, `create`, `update`, `delete`, plus `items`, `item-read`, `item-create`, `item-update`, `item-delete` for the media-query variants.

  ```bash
  contao-ai-cli --json image-size create --theme 1 --name "Tourenbild" \
      --set width=1600 --set sizes="(max-width: 1100px) 100vw, 1000px"
  contao-ai-cli --json image-size item-create --size 6 --media "(max-width: 767px)" --set width=400
  ```

  `list` and `items` are **presets over `contao:record:list`**, not new server commands. The generic command already reads any table correctly; what it cannot know is which six of the seventeen columns someone looking at an image size wants. That is the only thing the wrapper adds — and it puts `sizes` and `densities` next to `width` on purpose, because those are what the browser evaluates to pick a variant. A listing showing width alone invites choosing a size by its number and being served a different one.

  Requires core-bundle **v0.2.18** for the write commands; the `list`/`items` presets work against v0.2.17.

- **`theme` group, and `layout` grown from one command to five.** `theme list|read|create|update|delete` and `layout list|create|update|delete` alongside the `read` it already had — until today the only command the theme layer had at all.

  ```bash
  contao-ai-cli --json layout create --theme 1 --name "1 column" --template fe_page --set width=1200
  contao-ai-cli --json layout update 25 --set width=90 --set width_unit=vw
  ```

  `layout create` requires `--template` and offers no default: the option list depends on whether the layout is legacy or Twig and needs a live DataContainer to resolve, so no create command can know it. The layout also arrives without sections and modules, both of which are wizard columns holding serialized structures — and a layout without modules renders nothing.

  The five unit fields (`width`, `headerHeight`, `footerHeight`, `widthLeft`, `widthRight`) take a plain number and keep the record's existing unit; `--set <field>_unit=vw` changes the unit itself.

  `theme delete` is the widest cascade this CLI can trigger — modules, layouts, image sizes and the sizes' variants underneath. The confirmation prompt names them rather than saying "and its children", because the difference between deleting a layout and deleting a theme is four orders of magnitude on a real site.

  `theme create --author` is a free-text credit line, not a user reference.

- **`module` group — the theme layer is complete.** `types`, `list`, `read`, `create`, `update`, `delete`.

  ```bash
  contao-ai-cli --json module types
  contao-ai-cli --json module create --theme 1 --name "News - Latest" --type newslist \
      --set news_archives=1 --set numberOfItems=5
  ```

  **`module types` exists because the alternative is discovery by failure.** 45 types, and what each needs beyond a name depends on its DCA palette — 21 need nothing more, 24 do. Without a way to ask, a caller finds out by guessing a type and reading the error, which is a poor contract for a tool driven by an agent.

  Nothing about that mapping lives on this side: the server computes it from the DCA, so types registered by extensions appear too. `list` raises the page size to 100 because the demo theme alone holds 41 modules and the server's default of 20 would quietly show half a theme.

  Multi-value fields take a comma list — `--set news_archives=1,3`, `--set pages=2,3`.

## v0.7.0 - 2026-08-31

### Added

- **`record list` and `record schema` — any table that has a DCA.** Every other read group here is tied to one entity, so a table without a dedicated command was simply unreachable: the theme-level ones (`tl_image_size`, `tl_theme`, `tl_module`) and everything a third-party extension registers. The server loads the table's DCA and derives the readable, sortable and filterable columns from it, so an extension's table behaves exactly like a core one.

  ```bash
  contao-ai-cli --json record list tl_image_size --fields id,name,width,sizes,densities
  contao-ai-cli --json record list tl_page --filter published=1 --limit 50
  contao-ai-cli --json record schema tl_image_size
  ```

  The commands behind this — `contao:record:list` and `contao:dca:schema` — have been in the core bundle since its early releases. Their only caller was `RecordListTool` / `MetaTool` in contao-ai-backend-bundle: they were built for the browser chat, and this CLI never reached for them. So this is not a new capability on the server, it is a wire that was never run. Worth saying plainly, because it is the second time — the fifteen missing write commands of v0.5.0 were the same shape, and were also found by asking what the server could do rather than what the CLI offered.

  In the backend those commands are gated to ten hard-coded tables, because a backend user's reach has to follow their module permissions. Over SSH that gate buys nothing — whoever can run this already has full database access — so nothing is filtered on this side, and no allow-list is duplicated here to drift out of step with the server's.

  **Reading only.** There is deliberately no generic write: Contao has no path that puts an arbitrary field into an arbitrary table. Its generic writer is `DC_Table`, and that runs the whole DCA machinery — `save_callback`, `load_callback`, `mandatory`, `rgxp`, `unique`, versioning. A `record update --set field=value` over raw fields would skip all of it.

  Works against core-bundle v0.2.16, but **v0.2.17 is strongly recommended**: wiring this up is what exposed four bugs in `contao:record:list`, and without that release a `fileTree` column comes back destroyed, an unknown `--fields` column answers with a stack trace, and five tables of a stock 5.7 install exit 255 rather than listing.

### Fixed

- **A failing command threw away the server's explanation of why.** Every core-bundle command answers a failure with `{"status":"error","message":"..."}` on stdout and *then* exits 1. `run()` saw the exit code, raised, and reported stderr — so `page read 99999` explained a missing record with whatever PHP had printed at startup. On one live install that is a warning about ionCube and a missing `imagick.so`, i.e. a shared-library path where the sentence "Page not found: 99999" belonged.

  This is the same shape as the swallowed bulk-update summary of 2026-08-29: the server exits non-zero *and* explains itself, and the exit code was allowed to discard the explanation. That one was fixed at its single call site with `check=False`; this belongs in the raise itself, because every command that can fail was affected — `page`, `layout`, `news`, all of them.

- **A failure the caller could act on unwound a Python traceback.** `ContaoBackendError` is now a `click.ClickException`, so a record that does not exist, a table without a DCA or a refused SSH connection prints as one `Error: …` line. Only `connect` and `health` caught it before; every other command let it through raw, and an agent reading that had to work out that the last line was the message and the twelve above it were noise. Exit code and stderr are unchanged, so scripts behave exactly as before.

## v0.6.0 - 2026-08-29

### Added

- **`--ids` and `--ids-from-file` on every entity update command.** `page update --ids=39,40,41 --set max_teiln=4`, or `--ids-from-file ids.txt` with one ID per line (`#` starts a comment). Available on `page`, `news`, `event`, `faq`, `article` and `content`.

  Setting one field on 174 pages took about four minutes: 1.4 s per record, of which **0.67 s was establishing the SSH connection and nothing else**. The gap this fills is between `contao:page:update`, which is deterministic and versioned but takes exactly one ID, and `bridge rewrite`, which handles many records but is an LLM loop — a language model is the wrong instrument for writing a constant, and it bills API tokens to do it.

  One connection and one console invocation, but **still one version per record on the server**: the audit trail is the entire reason writes take this detour, and it was never the slow part. The response is a summary (`total`, `succeeded`, `failed`, `ids`, `errors`).

  Requires contao-ai-core-bundle **v0.2.15** or newer on the target. The positional ID keeps working exactly as before, with an unchanged response shape.

- **`health` reports the Contao version.** It named our three parts — CLI, core bundle, bridge — and said nothing about the Contao underneath, although the session can read it from composer at any time. During the advisory round of 2026-08-25 (eleven advisories, patched in 5.3.50 / 5.7.12) answering "is any of our sessions on a vulnerable Contao?" therefore meant logging in past `health` and reading the file by hand. A site an AI agent writes to is the last place an outdated Contao should sit unnoticed.

  It costs no extra round-trip — the call that fetches the bundle versions takes a package list. No verdict is attached: judging "current" needs a maintained minimum per branch (5.3 LTS vs 5.7), and a guessed traffic light would be worse than none.

### Fixed

- **Any output carrying a character outside the console encoding killed the command.** `page read 98` ended in `UnicodeEncodeError: 'charmap' codec can't encode character '�'` from inside `click.echo`. `_output()` serialises with `ensure_ascii=False`, which does not survive the cp1252 stdout that redirected output, CI, cron and any agent harness capturing stdout get on a German Windows.

  This is the fifth round of the same problem, and the first that no source-level guard could have caught: rounds one to four (v0.3.0, v0.3.1, v0.3.2, v0.4.2) each removed a character from our own code, and `test_output_encoding.py` keeps that clean — but this character came out of a *record*. The next one arrives with the next umlaut a customer types.

  `configure_output_encoding()` therefore puts stdout and stderr on UTF-8 at the entry point, covering the whole class instead of one more symbol. It is silent on a stream that cannot be reconfigured, and the ASCII fallback in `repl_skin.py` still stands behind it.

  The character itself turned out to be a core-bundle bug, fixed in v0.2.15: a binary file UUID was being emitted as text and mangled server-side.

- **SSH drained the caller's stdin.** `subprocess.run()` was called without an explicit `stdin`, so the child inherited ours. A `while read id; do contao-ai-cli … ; done < ids.txt` loop therefore ran **exactly once** — ssh had swallowed the rest of the list on the first iteration — and reported "1 processed, 1 succeeded, 0 failed" with exit code 0. Nothing failed, which is what made it dangerous; it was caught only by counting rows in the database afterwards.

  All three subprocess call sites now pass `stdin=subprocess.DEVNULL`; none of these commands has anything to read from stdin. A test fails if a new call site omits it.

### Changed

- **`CLAUDE.md` and `README.md` now say what the audit trail does *not* cover.** Both described precisely what a write records — `tl_log` for 7 days, `tl_version` permanently, `tl_undo` on deletion — and neither drew the boundary. An agent reads there what the CLI logs, and nowhere that raw SQL logs nothing.

  The shortcut is not exotic: every user of this CLI has SSH access, because the CLI cannot work without it, and the session file names the host, the user and the Contao root. A row changed with `mysql` has no version, no undo entry and no log line — no error either, just an empty version list nobody thinks to check. Serialised columns additionally break in silence under a `REPLACE()`. Reading with `SELECT`, `SHOW` or `mysqldump` is explicitly fine and often the shorter path.

### Notes

Suite: 349 tests, 16 skipped (325 before).

## v0.5.2 - 2026-08-25

### Fixed

- **`health` called every unreleased working copy out of date.** The update check was `latest != __version__`, so running v0.5.1 with v0.5.0 as the newest release printed `CLI v0.5.1 -> update available: v0.5.0` - an arrow pointing backwards, and a "re-run connect to install available updates" tip underneath it. String comparison also gets the ordering wrong once a segment reaches two digits: `'0.2.9' > '0.2.13'` lexicographically, which is exactly the range the core bundle is in.

  Comparison is now numeric and one-directional (`is_newer_version()`), applied to the CLI check in `health` and `connect` and to the core-bundle check in both. Versions that are not plain releases - `dev-main`, `1.0.0-beta` - compare as "cannot tell" and stay silent, because a wrong arrow is worse than no arrow.

  No dependency added: `packaging` is not installed alongside a pipx-installed CLI.

### Notes

7 new tests covering the ordering, the two-digit case, differing precision (`0.5` vs `0.5.0`) and the unparsable inputs. Suite at 315.

## v0.5.1 - 2026-08-25

### Fixed

- **`health` reported "Bridge not configured" for a server that had no bridge at all.** The line was derived solely from whether the session file carried a `bridge_url` and `bridge_token`; whether contao-ai-backend-bundle was actually installed on the target was never checked. Both cases printed the same words, and they call for opposite next steps - "not configured" reads as *installed, needs a token*, so you go and set a token into nothing.

  Found during the live rollout on web.werk.wien: `health` said exactly the same thing before and after the bundle was installed.

  The bridge line now has three states - `not installed`, `installed, not configured`, `ready` - plus `unknown` when the server could not be reached, which is not the same as "not installed" and no longer pretends to be. A session that carries a token for a server without the bundle is called out explicitly rather than reported as ready.

  In `--json`, `bridge` gains `state` and `installed` alongside the existing `configured`.

### Changed

- `get_installed_package_versions()` replaces the single-package lookup, so `health` reads both bundles out of `vendor/composer/installed.json` in one SSH round-trip instead of two. `get_core_bundle_installed_version()` stays as a thin wrapper for the connect flow.

### Notes

Verified live against c5 (both bundles present -> `ready`) and web.werk.wien (core v0.2.10 with an update available, bridge `ready`), plus a real SSH probe for a package that is not installed, which comes back as `None` rather than an error. 13 new tests, suite at 308.

## v0.5.0 — 2026-08-24

### Added

- **15 commands that the core bundle always had and the CLI never wrapped.** `update` and `delete` for `page`, `article`, `content`, `news`, `event` and `faq`; `page publish`; `comment delete` and `comment publish`; plus `news repair-headlines`. Until now the CLI could create and read content but not change it — while `README.md` promised `page … update, delete, publish` and `CLAUDE.md` gave two literal examples for commands that did not exist. That is the agent guide: exactly what a caller reads to decide what to invoke.

  It was never a deliberate split. `_require_bridge()` looked like evidence for one, but it only ever checked whether the core bundle was installed (see below), and the HTTP bridge allows exactly two tools, `record_clone` and `record_rewrite` — no deterministic field write exists there at all.

- `--yes` on every `delete`, and a confirmation prompt when there is a terminal to answer it. The Contao back end asks too: `DefaultOperationsListener` puts `onclick="if(!confirm(…))return false"` on the generic delete operation of every DCA. A prompt is therefore consistent with Contao rather than stricter — but an agent or a cron job has nobody to answer, so it only appears on a TTY. `member delete` and `user delete`, which had no guard at all, are covered now too.

- Two tests that pin the documentation to the command tree: the README table is generated from it, and every `contao-ai-cli …` example in README and CLAUDE.md must resolve to a real command with real options. They immediately found three more stale examples — `page read --id 1`, `article list --pid`, and a whole `schema dca` / `schema module` pair that has never existed.

### Fixed

- `get_core_bundle_latest_version()` read `packagist.org/packages/<name>.json`, which is cached and lags: it still reported v0.2.7 after v0.2.9 was released. It now uses `repo.packagist.org/p2/<name>.json`, the metadata Composer itself resolves against, so `connect` and `health` no longer report "up to date" while an update is waiting.
- A malformed `--set` is an error instead of being dropped. `--set "title Neu"` used to vanish silently and report a successful update that changed nothing.

### Changed

- `_require_bridge()` → `_require_core_bundle()`, `_detect_bridge()` → `_detect_core_bundle()`, and the session key `bridge_available` → `core_bundle_available`. "Bridge" meant two unrelated things: the core bundle, after its original name `contao-cli-bridge`, and the HTTP endpoint into contao-ai-backend-bundle. The collision was read as evidence of a design decision that had never been made. Sessions written before this release are still understood — the old key is read as a fallback.
- README's command table is generated from the command tree and pinned by a test, so it cannot drift again.

### Notes

Requires **contao-ai-core-bundle v0.2.10** for `page publish` / `comment publish`; `unpublish` threw on strict-SQL servers before that. Deleting cascades to child records since core-bundle v0.2.8 and stays recoverable from the back end's *Restore* module.

Verified live on Contao 5.7.11: create, update, publish, unpublish, a rejected malformed `--set`, a declined delete that left the record in place, and a piped delete that cascaded to 3 rows with no orphans left behind.

## v0.4.4 — 2026-08-24

### Fixed

- **The REPL could not start unless the console was already at code page 65001.** `ReplSkin` printed box drawing, a diamond, a checkmark and a chevron unconditionally, so `print()` raised `UnicodeEncodeError` on the very first line of the banner. Measured against the encodings a Windows console actually uses: only UTF-8 carries the full set. cp1252 fails on all 21 glyphs; cp850 and cp437 — the classic console defaults — carry the straight lines and shading blocks but fail on the rounded corners, the diamond, the checkmark and the chevron, 12 of 22.

### Changed

- Every character the skin prints now comes from one of two glyph tables, and the table is chosen once per instance from `sys.stdout.encoding` rather than symbol by symbol. The ASCII fallback uses `+-|` for structure and the `[OK]` / `[X]` / `[!]` / `[i]` markers the rest of the CLI already uses. A terminal that can render Unicode sees exactly what it saw before.
- `ReplSkin(..., ascii_only=True|False)` forces a set; `CONTAO_AI_CLI_ASCII=1` forces ASCII from the environment, for a UTF-8 terminal whose font lacks the glyphs.

### Added

- `contao_ai_cli/tests/test_output_encoding.py`. The skin is covered behaviourally — every output method is exercised and the captured result must encode to cp1252 — because a lexical rule cannot distinguish the glyph table from a printed literal. Every other module is checked by an AST pass over its string literals, module docstrings excluded since Click never prints them. That pass replaces the narrower one added in v0.4.2. Suite goes from 180 to 257.

### Notes

The REPL still needs a real Windows console: `prompt_toolkit` raises `NoConsoleScreenBufferError` on a piped stdin regardless of encoding. That is unrelated and unchanged.

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
