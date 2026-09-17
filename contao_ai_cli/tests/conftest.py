import pytest


@pytest.fixture(autouse=True)
def _no_update_notice(monkeypatch):
    monkeypatch.setenv("CONTAO_AI_CLI_NO_UPDATE_CHECK", "1")
