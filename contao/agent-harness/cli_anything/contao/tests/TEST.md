# Test Plan — cli-anything-contao

## Overview

Tests for the cli-anything-contao CLI harness. The CLI wraps Contao 5's
Symfony Console (`php bin/console`) via SSH. The real Contao installation
is a hard dependency.

## Test Inventory Plan

| File | Type | Planned Tests |
|---|---|---|
| `test_core.py` | Unit tests (no SSH) | ~20 |
| `test_full_e2e.py` | E2E tests (real SSH + Contao) | ~15 |

## Unit Test Plan (test_core.py)

### session.py
- `test_save_and_load_session` — save config, reload, verify fields
- `test_delete_session` — save then delete, verify gone
- `test_list_sessions` — create multiple sessions, list them
- `test_load_missing_session` — returns empty dict

### contao_backend.py
- `test_missing_session_file_raises` — ContaoBackendError if no session file
- `test_incomplete_session_raises` — ContaoBackendError if missing required fields
- `test_ssh_command_building` — verify _ssh_args() output
- `test_default_key_fallback` — uses id_ed25519 if exists

### contao_cli.py (Click commands)
- `test_cli_help` — --help exits 0
- `test_cache_clear_help` — cache clear --help
- `test_user_list_help` — user list --help
- `test_backup_create_help` — backup create --help
- `test_connect_missing_args` — missing --host exits non-zero

## E2E Test Plan (test_full_e2e.py)

Requires: SSH access to a Contao installation, session configured via `CONTAO_TEST_HOST` env var.

### Connection
- `test_connect_and_save_session` — connect, verify session file created
- `test_version_command` — --version exits 0

### Cache
- `test_cache_clear` — clears cache, exit 0
- `test_cache_warmup` — warms cache, exit 0

### Contao Operations
- `test_migrate_dry_run` — dry-run migration, no changes
- `test_maintenance_status` — reads maintenance mode status
- `test_cron_list` — lists cron jobs

### Users
- `test_user_list_returns_data` — at least one user returned

### Backup
- `test_backup_create_and_list` — create backup, verify in list

### Debug
- `test_debug_plugins` — lists plugins, exit 0

## Workflow Scenarios

### Scenario 1: Deployment Pipeline
1. `contao maintenance enable` — take site offline
2. `contao migrate` — run migrations
3. `cache clear` — clear cache
4. `contao filesync` — sync file system
5. `contao maintenance disable` — bring site online

### Scenario 2: User Management
1. `user list` — see existing users
2. `user create` — add new user
3. `user list` — verify created

### Scenario 3: Backup & Restore
1. `backup create` — create backup
2. `backup list` — verify backup present

---

## Test Results

*(Appended after test run)*
