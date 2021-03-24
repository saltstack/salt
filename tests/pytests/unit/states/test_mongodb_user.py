"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.mongodb_user as mongodb_user
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {mongodb_user: {"__opts__": {"test": True}}}


def test_present():
    """
    Test to ensure that the user is present with the specified properties.
    """
    name = "myapp"
    passwd = "password-of-myapp"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Port ({}) is not an integer."
    ret.update({"comment": comt})
    assert mongodb_user.present(name, passwd, port={}) == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=[])
    with patch.dict(
        mongodb_user.__salt__,
        {"mongodb.user_create": mock_t, "mongodb.user_find": mock_f},
    ):
        comt = ("User {} is not present and needs to be created").format(name)
        ret.update({"comment": comt, "result": None})
        assert mongodb_user.present(name, passwd) == ret

        with patch.dict(mongodb_user.__opts__, {"test": True}):
            comt = "User {} is not present and needs to be created".format(name)
            ret.update({"comment": comt, "result": None})
            assert mongodb_user.present(name, passwd) == ret

        with patch.dict(mongodb_user.__opts__, {"test": False}):
            comt = "User {} has been created".format(name)
            ret.update({"comment": comt, "result": True, "changes": {name: "Present"}})
            assert mongodb_user.present(name, passwd) == ret


def test_absent():
    """
    Test to ensure that the named user is absent.
    """
    name = "myapp"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, True, False])
    mock_t = MagicMock(return_value=True)
    with patch.dict(
        mongodb_user.__salt__,
        {"mongodb.user_exists": mock, "mongodb.user_remove": mock_t},
    ):
        with patch.dict(mongodb_user.__opts__, {"test": True}):
            comt = "User {} is present and needs to be removed".format(name)
            ret.update({"comment": comt, "result": None})
            assert mongodb_user.absent(name) == ret

        with patch.dict(mongodb_user.__opts__, {"test": False}):
            comt = "User {} has been removed".format(name)
            ret.update({"comment": comt, "result": True, "changes": {name: "Absent"}})
            assert mongodb_user.absent(name) == ret

        comt = "User {} is not present".format(name)
        ret.update({"comment": comt, "result": True, "changes": {}})
        assert mongodb_user.absent(name) == ret
