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
contao-ai-cli connect \
  --host your-server.example.com \
  --user ssh-username \
  --root /var/www/contao \
  --key ~/.ssh/id_ed25519
```

## Run Tests

```bash
# Unit tests only (no SSH required)
pytest cli_anything/contao/tests/test_core.py -v

# E2E tests (SSH required)
# Set connection details via environment variables — never hardcode credentials.
# IMPORTANT: MSYS_NO_PATHCONV=1 is required on Windows/Git Bash to prevent
# path conversion of Unix paths in environment variables.
MSYS_NO_PATHCONV=1 \
  CONTAO_TEST_HOST=your-server.example.com \
  CONTAO_TEST_USER=ssh-username \
  CONTAO_TEST_ROOT=/var/www/contao \
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
