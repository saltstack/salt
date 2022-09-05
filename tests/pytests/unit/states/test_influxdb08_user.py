"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.influxdb08_user as influxdb08_user
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {influxdb08_user: {}}


def test_present():
    """
    Test to ensure that the cluster admin or database user is present.
    """
    name = "salt"
    passwd = "salt"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[False, False, False, True])
    mock_t = MagicMock(side_effect=[True, False])
    mock_f = MagicMock(return_value=False)
    with patch.dict(
        influxdb08_user.__salt__,
        {
            "influxdb08.db_exists": mock_f,
            "influxdb08.user_exists": mock,
            "influxdb08.user_create": mock_t,
        },
    ):
        comt = "Database mydb does not exist"
        ret.update({"comment": comt})
        assert influxdb08_user.present(name, passwd, database="mydb") == ret

        with patch.dict(influxdb08_user.__opts__, {"test": True}):
            comt = "User {} is not present and needs to be created".format(name)
            ret.update({"comment": comt, "result": None})
            assert influxdb08_user.present(name, passwd) == ret

        with patch.dict(influxdb08_user.__opts__, {"test": False}):
            comt = "User {} has been created".format(name)
            ret.update(
                {"comment": comt, "result": True, "changes": {"salt": "Present"}}
            )
            assert influxdb08_user.present(name, passwd) == ret

            comt = "Failed to create user {}".format(name)
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert influxdb08_user.present(name, passwd) == ret

        comt = "User {} is already present".format(name)
        ret.update({"comment": comt, "result": True})
        assert influxdb08_user.present(name, passwd) == ret


def test_absent():
    """
    Test to ensure that the named cluster admin or database user is absent.
    """
    name = "salt"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, True, True, False])
    mock_t = MagicMock(side_effect=[True, False])
    with patch.dict(
        influxdb08_user.__salt__,
        {"influxdb08.user_exists": mock, "influxdb08.user_remove": mock_t},
    ):
        with patch.dict(influxdb08_user.__opts__, {"test": True}):
            comt = "User {} is present and needs to be removed".format(name)
            ret.update({"comment": comt})
            assert influxdb08_user.absent(name) == ret

        with patch.dict(influxdb08_user.__opts__, {"test": False}):
            comt = "User {} has been removed".format(name)
            ret.update({"comment": comt, "result": True, "changes": {"salt": "Absent"}})
            assert influxdb08_user.absent(name) == ret

            comt = "Failed to remove user {}".format(name)
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert influxdb08_user.absent(name) == ret

        comt = "User {} is not present, so it cannot be removed".format(name)
        ret.update({"comment": comt, "result": True})
        assert influxdb08_user.absent(name) == ret
