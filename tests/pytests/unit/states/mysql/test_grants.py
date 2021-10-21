"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.mysql_grants as mysql_grants
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {mysql_grants: {}}


def test_present():
    """
    Test to ensure that the grant is present with the specified properties.
    """
    name = "frank_exampledb"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, False, False, False])
    mock_t = MagicMock(return_value=True)
    mock_str = MagicMock(return_value="salt")
    mock_none = MagicMock(return_value=None)
    with patch.dict(
        mysql_grants.__salt__,
        {"mysql.grant_exists": mock, "mysql.grant_add": mock_t},
    ):
        comt = "Grant None on None to None@localhost is already present"
        ret.update({"comment": comt})
        assert mysql_grants.present(name) == ret

        with patch.object(mysql_grants, "_get_mysql_error", mock_str):
            ret.update({"comment": "salt", "result": False})
            assert mysql_grants.present(name) == ret

        with patch.object(mysql_grants, "_get_mysql_error", mock_none):
            with patch.dict(mysql_grants.__opts__, {"test": True}):
                comt = "MySQL grant frank_exampledb is set to be created"
                ret.update({"comment": comt, "result": None})
                assert mysql_grants.present(name) == ret

            with patch.dict(mysql_grants.__opts__, {"test": False}):
                comt = "Grant None on None to None@localhost has been added"
                ret.update(
                    {"comment": comt, "result": True, "changes": {name: "Present"}}
                )
                assert mysql_grants.present(name) == ret


def test_absent():
    """
    Test to ensure that the grant is absent.
    """
    name = "frank_exampledb"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, False])
    mock_t = MagicMock(side_effect=[True, True, True, False, False])
    mock_str = MagicMock(return_value="salt")
    mock_none = MagicMock(return_value=None)
    with patch.dict(
        mysql_grants.__salt__,
        {"mysql.grant_exists": mock_t, "mysql.grant_revoke": mock},
    ):
        with patch.dict(mysql_grants.__opts__, {"test": True}):
            comt = "MySQL grant frank_exampledb is set to be revoked"
            ret.update({"comment": comt, "result": None})
            assert mysql_grants.absent(name) == ret

        with patch.dict(mysql_grants.__opts__, {"test": False}):
            comt = "Grant None on None for None@localhost has been revoked"
            ret.update({"comment": comt, "result": True, "changes": {name: "Absent"}})
            assert mysql_grants.absent(name) == ret

            with patch.object(mysql_grants, "_get_mysql_error", mock_str):
                comt = "Unable to revoke grant None on None for None@localhost (salt)"
                ret.update({"comment": comt, "result": False, "changes": {}})
                assert mysql_grants.absent(name) == ret

                comt = (
                    "Unable to determine if grant None on "
                    "None for None@localhost exists (salt)"
                )
                ret.update({"comment": comt})
                assert mysql_grants.absent(name) == ret

        with patch.object(mysql_grants, "_get_mysql_error", mock_none):
            comt = (
                "Grant None on None to None@localhost is not present,"
                " so it cannot be revoked"
            )
            ret.update({"comment": comt, "result": True})
            assert mysql_grants.absent(name) == ret
