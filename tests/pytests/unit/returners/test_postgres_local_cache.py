"""
Unit tests for the postgres_local_cache.
"""

import json

import pytest

import salt.returners.postgres_local_cache as postgres_local_cache
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(tmp_path):
    return {
        postgres_local_cache: {
            "__opts__": {
                "cachedir": str(tmp_path / "cache_dir"),
                "keep_jobs_seconds": 3600,
            }
        }
    }


def test_returner():
    """
    Tests that the returner function
    """
    load = {
        "tgt_type": "glob",
        "fun_args": [],
        "jid": "20200108221839189167",
        "return": True,
        "retcode": 0,
        "success": True,
        "tgt": "minion",
        "cmd": "_return",
        "_stamp": "2020-01-08T22:18:39.197774",
        "arg": [],
        "fun": "test.ping",
        "id": "minion",
    }

    expected = {"return": "True", "retcode": 0, "success": True}

    connect_mock = MagicMock()
    with patch.object(postgres_local_cache, "_get_conn", connect_mock):
        postgres_local_cache.returner(load)

        return_val = None
        for call in connect_mock.mock_calls:
            for arg in call.args:
                if isinstance(arg, tuple):
                    for val in arg:
                        if isinstance(val, str) and "return" in val:
                            return_val = json.loads(val)

        assert return_val is not None, None
        assert return_val == expected


def test_returner_unicode_exception():
    """
    Tests that the returner function
    """
    return_val = "Trüe"

    load = {
        "tgt_type": "glob",
        "fun_args": [],
        "jid": "20200108221839189167",
        "return": return_val,
        "retcode": 0,
        "success": True,
        "tgt": "minion",
        "cmd": "_return",
        "_stamp": "2020-01-08T22:18:39.197774",
        "arg": [],
        "fun": "test.ping",
        "id": "minion",
    }

    expected = {"return": "Trüe", "retcode": 0, "success": True}

    connect_mock = MagicMock()
    with patch.object(postgres_local_cache, "_get_conn", connect_mock):
        postgres_local_cache.returner(load)

        return_val = None
        search_string = "return"
        for call in connect_mock.mock_calls:
            for arg in call.args:
                if isinstance(arg, tuple):
                    for val in arg:
                        if isinstance(val, str):
                            if search_string in val:
                                return_val = json.loads(val)

        assert return_val is not None, None
        assert return_val == expected
