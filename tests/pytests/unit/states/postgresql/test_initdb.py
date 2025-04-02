"""
    :codeauthor: Andrew Colin Kissa <andrew@topdog.za.net>
"""

import pytest

import salt.states.postgres_initdb as postgres_initdb
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {postgres_initdb: {}}


def test_present_existing():
    """
    Test existing data directory handled correctly
    """
    name = "/var/lib/psql/data"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    with patch.dict(postgres_initdb.__salt__, {"postgres.datadir_exists": mock_true}):
        _comt = f"Postgres data directory {name} is already present"
        ret.update({"comment": _comt, "result": True})
        assert postgres_initdb.present(name) == ret


def test_present_non_existing_pass():
    """
    Test non existing data directory ok
    """
    name = "/var/lib/psql/data"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        postgres_initdb.__salt__,
        {"postgres.datadir_exists": mock_false, "postgres.datadir_init": mock_true},
    ):
        with patch.dict(postgres_initdb.__opts__, {"test": True}):
            _comt = f"Postgres data directory {name} is set to be initialized"
            ret.update({"comment": _comt, "result": None})
            assert postgres_initdb.present(name) == ret

        with patch.dict(postgres_initdb.__opts__, {"test": False}):
            _comt = f"Postgres data directory {name} has been initialized"
            _changes = {name: "Present"}
            ret.update({"comment": _comt, "result": True, "changes": _changes})
            assert postgres_initdb.present(name) == ret


def test_present_non_existing_fail():
    """
    Test non existing data directory fail
    """
    name = "/var/lib/psql/data"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        postgres_initdb.__salt__,
        {"postgres.datadir_exists": mock_false, "postgres.datadir_init": mock_false},
    ):
        with patch.dict(postgres_initdb.__opts__, {"test": False}):
            _comt = f"Postgres data directory {name} initialization failed"
            ret.update({"comment": _comt, "result": False})
            assert postgres_initdb.present(name) == ret
