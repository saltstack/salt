import secrets

import pytest

import salt.states.file as file
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def configure_loader_modules():
    return {
        file: {"__opts__": {"test": False}},
    }


def test_cached_test_true():
    name = "salt://test/file.exe"
    source_hash = secrets.token_hex(nbytes=32)
    expected = {
        "changes": {},
        "comment": f"File will be cached: {name}",
        "name": name,
        "result": None,
    }
    salt = {
        "cp.is_cached": MagicMock(return_value=""),
        "file.get_source_sum": MagicMock(return_value={"hsum": source_hash}),
    }
    opts = {"test": True}
    with patch.dict(file.__salt__, salt), patch.dict(file.__opts__, opts):
        result = file.cached(name=name, source_hash=source_hash)
    assert result == expected


def test_cached_present_test_true():
    name = "salt://test/file.exe"
    source_hash = secrets.token_hex(nbytes=32)
    expected = {
        "changes": {},
        "comment": f"File already cached: {name}",
        "name": name,
        "result": None,
    }
    salt = {
        "cp.is_cached": MagicMock(return_value="path/to/file"),
        "file.get_hash": MagicMock(return_value=source_hash),
        "file.get_source_sum": MagicMock(return_value={"hsum": source_hash}),
    }
    opts = {"test": True, "hash_type": "sha256"}
    with patch.dict(file.__salt__, salt), patch.dict(file.__opts__, opts):
        result = file.cached(name=name, source_hash=source_hash)
    assert result == expected


def test_cached_present_different_hash_test_true():
    name = "salt://test/file.exe"
    source_hash = secrets.token_hex(nbytes=32)
    existing_hash = secrets.token_hex(nbytes=32)
    expected = {
        "changes": {},
        "comment": f"Hashes don't match.\nFile will be cached: {name}",
        "name": name,
        "result": None,
    }
    salt = {
        "cp.is_cached": MagicMock(return_value="path/to/file"),
        "file.get_hash": MagicMock(return_value=existing_hash),
        "file.get_source_sum": MagicMock(return_value={"hsum": source_hash}),
    }
    opts = {"test": True, "hash_type": "sha256"}
    with patch.dict(file.__salt__, salt), patch.dict(file.__opts__, opts):
        result = file.cached(name=name, source_hash=source_hash)
    assert result == expected


def test_cached_present_no_source_hash_test_true():
    name = "salt://test/file.exe"
    existing_hash = secrets.token_hex(nbytes=32)
    expected = {
        "changes": {},
        "comment": f"No hash found. File will be cached: {name}",
        "name": name,
        "result": None,
    }
    salt = {
        "cp.is_cached": MagicMock(return_value="path/to/file"),
        "file.get_hash": MagicMock(return_value=existing_hash),
    }
    opts = {"test": True, "hash_type": "sha256"}
    with patch.dict(file.__salt__, salt), patch.dict(file.__opts__, opts):
        result = file.cached(name=name)
    assert result == expected
