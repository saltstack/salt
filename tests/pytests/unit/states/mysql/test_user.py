"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.mysql_user as mysql_user
import salt.utils.data
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {mysql_user: {}}


def test_present():
    """
    Test to ensure that the named user is present with
    the specified properties.
    """
    name = "frank"
    password = "bob@cat"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock = MagicMock(
        side_effect=[
            True,
            False,
            True,
            False,
            False,
            True,
            False,
            False,
            False,
            False,
            False,
            True,
        ]
    )
    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    mock_str = MagicMock(return_value="salt")
    mock_none = MagicMock(return_value=None)
    mock_sn = MagicMock(side_effect=[None, "salt", None, None, None])
    with patch.object(salt.utils.data, "is_true", mock_f):
        comt = (
            "Either password or password_hash must be specified,"
            " unless allow_passwordless is True"
        )
        ret.update({"comment": comt})
        assert mysql_user.present(name) == ret

    with patch.dict(
        mysql_user.__salt__,
        {"mysql.user_exists": mock, "mysql.user_chpass": mock_t},
    ):
        with patch.object(salt.utils.data, "is_true", mock_t):
            comt = "User frank@localhost is already present with passwordless login"
            ret.update({"comment": comt, "result": True})
            assert mysql_user.present(name, allow_passwordless=True) == ret

            with patch.object(mysql_user, "_get_mysql_error", mock_str):
                ret.update({"comment": "salt", "result": False})
                assert mysql_user.present(name) == ret

        with patch.object(mysql_user, "_get_mysql_error", mock_str):
            comt = "User frank@localhost is already present with the desired password"
            ret.update({"comment": comt, "result": True})
            assert mysql_user.present(name, password=password) == ret

            with patch.object(mysql_user, "_get_mysql_error", mock_str):
                ret.update({"comment": "salt", "result": False})
                assert mysql_user.present(name, password=password) == ret

            with patch.object(mysql_user, "_get_mysql_error", mock_none):
                with patch.dict(mysql_user.__opts__, {"test": True}):
                    comt = "Password for user frank@localhost is set to be changed"
                    ret.update({"comment": comt, "result": None})
                    assert mysql_user.present(name, password=password) == ret

            with patch.object(mysql_user, "_get_mysql_error", mock_sn):
                with patch.dict(mysql_user.__opts__, {"test": False}):
                    ret.update({"comment": "salt", "result": False})
                    assert mysql_user.present(name, password=password) == ret

                with patch.dict(mysql_user.__opts__, {"test": True}):
                    comt = "User frank@localhost is set to be added"
                    ret.update({"comment": comt, "result": None})
                    assert mysql_user.present(name, password=password) == ret

                with patch.dict(mysql_user.__opts__, {"test": False}):
                    comt = "Password for user frank@localhost has been changed"
                    ret.update(
                        {"comment": comt, "result": True, "changes": {name: "Updated"}}
                    )
                    assert mysql_user.present(name, password=password) == ret


def test_absent():
    """
    Test to ensure that the named user is absent.
    """
    name = "frank_exampledb"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, True, True, False, False, False])
    mock_t = MagicMock(side_effect=[True, False])
    mock_str = MagicMock(return_value="salt")
    mock_none = MagicMock(return_value=None)
    with patch.dict(
        mysql_user.__salt__,
        {"mysql.user_exists": mock, "mysql.user_remove": mock_t},
    ):
        with patch.dict(mysql_user.__opts__, {"test": True}):
            comt = "User frank_exampledb@localhost is set to be removed"
            ret.update({"comment": comt, "result": None})
            assert mysql_user.absent(name) == ret

        with patch.dict(mysql_user.__opts__, {"test": False}):
            comt = "User frank_exampledb@localhost has been removed"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "changes": {"frank_exampledb": "Absent"},
                }
            )
            assert mysql_user.absent(name) == ret

            with patch.object(mysql_user, "_get_mysql_error", mock_str):
                comt = "User frank_exampledb@localhost has been removed"
                ret.update({"comment": "salt", "result": False, "changes": {}})
                assert mysql_user.absent(name) == ret

                comt = "User frank_exampledb@localhost has been removed"
                ret.update({"comment": "salt"})
                assert mysql_user.absent(name) == ret

            with patch.object(mysql_user, "_get_mysql_error", mock_none):
                comt = (
                    "User frank_exampledb@localhost is not present,"
                    " so it cannot be removed"
                )
                ret.update({"comment": comt, "result": True, "changes": {}})
                assert mysql_user.absent(name) == ret
