"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.influxdb08_database as influxdb08_database
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {influxdb08_database: {}}


def test_present():
    """
    Test to ensure that the named database is present.
    """
    name = "salt"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[False, False, False, True])
    mock_t = MagicMock(side_effect=[True, False])
    with patch.dict(
        influxdb08_database.__salt__,
        {"influxdb08.db_exists": mock, "influxdb08.db_create": mock_t},
    ):
        with patch.dict(influxdb08_database.__opts__, {"test": True}):
            comt = f"Database {name} is absent and needs to be created"
            ret.update({"comment": comt})
            assert influxdb08_database.present(name) == ret

        with patch.dict(influxdb08_database.__opts__, {"test": False}):
            comt = f"Database {name} has been created"
            ret.update(
                {"comment": comt, "result": True, "changes": {"salt": "Present"}}
            )
            assert influxdb08_database.present(name) == ret

            comt = f"Failed to create database {name}"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert influxdb08_database.present(name) == ret

        comt = f"Database {name} is already present, so cannot be created"
        ret.update({"comment": comt, "result": True})
        assert influxdb08_database.present(name) == ret


def test_absent():
    """
    Test to ensure that the named database is absent.
    """
    name = "salt"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, True, True, False])
    mock_t = MagicMock(side_effect=[True, False])
    with patch.dict(
        influxdb08_database.__salt__,
        {"influxdb08.db_exists": mock, "influxdb08.db_remove": mock_t},
    ):
        with patch.dict(influxdb08_database.__opts__, {"test": True}):
            comt = f"Database {name} is present and needs to be removed"
            ret.update({"comment": comt})
            assert influxdb08_database.absent(name) == ret

        with patch.dict(influxdb08_database.__opts__, {"test": False}):
            comt = f"Database {name} has been removed"
            ret.update({"comment": comt, "result": True, "changes": {"salt": "Absent"}})
            assert influxdb08_database.absent(name) == ret

            comt = f"Failed to remove database {name}"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert influxdb08_database.absent(name) == ret

        comt = f"Database {name} is not present, so it cannot be removed"
        ret.update({"comment": comt, "result": True})
        assert influxdb08_database.absent(name) == ret
