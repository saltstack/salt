"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.postgres_database as postgres_database
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {postgres_database: {}}


def test_present():
    """
    Test to ensure that the named database is present
    with the specified properties.
    """
    name = "frank"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_t = MagicMock(return_value=True)
    mock = MagicMock(return_value={name: {}})
    with patch.dict(
        postgres_database.__salt__,
        {"postgres.db_list": mock, "postgres.db_alter": mock_t},
    ):
        comt = f"Database {name} is already present"
        ret.update({"comment": comt, "result": True})
        assert postgres_database.present(name) == ret

        comt = "Database frank has wrong parameters which couldn't be changed on fly."
        ret.update({"comment": comt, "result": False})
        assert postgres_database.present(name, tablespace="A", lc_collate=True) == ret

        with patch.dict(postgres_database.__opts__, {"test": True}):
            comt = "Database frank exists, but parameters need to be changed"
            ret.update({"comment": comt, "result": None})
            assert postgres_database.present(name, tablespace="A") == ret

        with patch.dict(postgres_database.__opts__, {"test": False}):
            comt = "Parameters for database frank have been changed"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "changes": {name: "Parameters changed"},
                }
            )
            assert postgres_database.present(name, tablespace="A") == ret


def test_absent():
    """
    Test to ensure that the named database is absent.
    """
    name = "frank"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_t = MagicMock(return_value=True)
    mock = MagicMock(side_effect=[True, True, False])
    with patch.dict(
        postgres_database.__salt__,
        {"postgres.db_exists": mock, "postgres.db_remove": mock_t},
    ):
        with patch.dict(postgres_database.__opts__, {"test": True}):
            comt = f"Database {name} is set to be removed"
            ret.update({"comment": comt, "result": None})
            assert postgres_database.absent(name) == ret

        with patch.dict(postgres_database.__opts__, {"test": False}):
            comt = f"Database {name} has been removed"
            ret.update({"comment": comt, "result": True, "changes": {name: "Absent"}})
            assert postgres_database.absent(name) == ret

            comt = f"Database {name} is not present, so it cannot be removed"
            ret.update({"comment": comt, "result": True, "changes": {}})
            assert postgres_database.absent(name) == ret
