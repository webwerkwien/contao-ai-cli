# cli-anything-contao

Agent-native CLI for Contao 5 CMS via SSH.

## Requirements

- Python 3.10+
- SSH access to a Contao 5 installation
- SSH key configured (see `~/.ssh/id_ed25519`)

## Install

```bash
cd contao/agent-harness
pip install -e .
```

## Connect

```bash
cli-anything-contao connect \
  --host c5.axeltest.at \
  --user c155929_C5 \
  --root /var/www/clients/client1/web246/web
```

## Run Tests

```bash
# Unit tests only (no SSH required)
pytest cli_anything/contao/tests/test_core.py -v

# E2E tests (SSH required)
# IMPORTANT: MSYS_NO_PATHCONV=1 is required on Windows/Git Bash to prevent
# path conversion of Unix paths in environment variables.
MSYS_NO_PATHCONV=1 CONTAO_TEST_HOST=c5.axeltest.at \
  CONTAO_TEST_USER=c155929_C5 \
  CONTAO_TEST_ROOT=/var/www/clients/client1/web246/web \
  pytest cli_anything/contao/tests/ -v -s

# Force installed command for E2E
MSYS_NO_PATHCONV=1 CLI_ANYTHING_FORCE_INSTALLED=1 \
  CONTAO_TEST_HOST=c5.axeltest.at \
  CONTAO_TEST_USER=c155929_C5 \
  CONTAO_TEST_ROOT=/var/www/clients/client1/web246/web \
  pytest cli_anything/contao/tests/ -v -s
```

## Basic Usage

```bash
cli-anything-contao cache clear
cli-anything-contao contao migrate
cli-anything-contao user list
cli-anything-contao backup create
cli-anything-contao --json user list   # JSON output for agents
cli-anything-contao repl               # Interactive REPL
```
