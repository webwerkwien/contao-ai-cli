import json
import os
import sys
import tempfile

import pytest

from cli_anything.contao.core.session import save_session


@pytest.mark.skipif(sys.platform == "win32", reason="chmod not reliable on Windows")
def test_save_session_creates_file_with_restricted_permissions():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        path = tmp.name
    try:
        save_session({"host": "example.com"}, path)
        mode = oct(os.stat(path).st_mode & 0o777)
        assert mode == oct(0o600), f"Expected 0o600, got {mode}"
    finally:
        os.unlink(path)


def test_save_session_writes_valid_json():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        path = tmp.name
    try:
        config = {"host": "example.com", "user": "deploy", "port": 22}
        save_session(config, path)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == config
    finally:
        os.unlink(path)


def test_save_session_overwrites_existing_file():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        path = tmp.name
    try:
        save_session({"host": "first.com"}, path)
        save_session({"host": "second.com"}, path)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == {"host": "second.com"}
    finally:
        os.unlink(path)
