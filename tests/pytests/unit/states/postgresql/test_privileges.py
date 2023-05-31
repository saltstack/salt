"""
    :codeauthor: Andrew Colin Kissa <andrew@topdog.za.net>
"""

import pytest

import salt.states.postgres_privileges as postgres_privileges
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {postgres_privileges: {}}


def test_present_table():
    """
    Test present
    """
    table_name = "awl"
    name = "baruwa"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        postgres_privileges.__salt__, {"postgres.has_privileges": mock_true}
    ):
        comt = "The requested privilege(s) are already set"
        ret.update({"comment": comt, "result": True})
        assert postgres_privileges.present(name, table_name, "table") == ret

    with patch.dict(
        postgres_privileges.__salt__,
        {
            "postgres.has_privileges": mock_false,
            "postgres.privileges_grant": mock_true,
        },
    ):
        with patch.dict(postgres_privileges.__opts__, {"test": True}):
            comt = "The privilege(s): {} are set to be granted to {}".format(
                "ALL", name
            )
            ret.update({"comment": comt, "result": None})
            assert (
                postgres_privileges.present(
                    name, table_name, "table", privileges=["ALL"]
                )
                == ret
            )

        with patch.dict(postgres_privileges.__opts__, {"test": False}):
            comt = "The privilege(s): {} have been granted to {}".format("ALL", name)
            ret.update(
                {"comment": comt, "result": True, "changes": {"baruwa": "Present"}}
            )
            assert (
                postgres_privileges.present(
                    name, table_name, "table", privileges=["ALL"]
                )
                == ret
            )


def test_present_group():
    """
    Test present group
    """
    group_name = "admins"
    name = "baruwa"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        postgres_privileges.__salt__,
        {
            "postgres.has_privileges": mock_false,
            "postgres.privileges_grant": mock_true,
        },
    ):
        with patch.dict(postgres_privileges.__opts__, {"test": True}):
            comt = "The privilege(s): {} are set to be granted to {}".format(
                group_name, name
            )
            ret.update({"comment": comt, "result": None})
            assert postgres_privileges.present(name, group_name, "group") == ret

        with patch.dict(postgres_privileges.__opts__, {"test": False}):
            comt = "The privilege(s): {} have been granted to {}".format(
                group_name, name
            )
            ret.update(
                {"comment": comt, "result": True, "changes": {"baruwa": "Present"}}
            )
            assert postgres_privileges.present(name, group_name, "group") == ret


def test_absent_table():
    """
    Test absent
    """
    table_name = "awl"
    name = "baruwa"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        postgres_privileges.__salt__, {"postgres.has_privileges": mock_false}
    ):
        with patch.dict(postgres_privileges.__opts__, {"test": True}):
            comt = "The requested privilege(s) are not set so cannot be revoked"
            ret.update({"comment": comt, "result": True})
            assert postgres_privileges.absent(name, table_name, "table") == ret

    with patch.dict(
        postgres_privileges.__salt__,
        {
            "postgres.has_privileges": mock_true,
            "postgres.privileges_revoke": mock_true,
        },
    ):
        with patch.dict(postgres_privileges.__opts__, {"test": True}):
            comt = "The privilege(s): {} are set to be revoked from {}".format(
                "ALL", name
            )
            ret.update({"comment": comt, "result": None})
            assert (
                postgres_privileges.absent(
                    name, table_name, "table", privileges=["ALL"]
                )
                == ret
            )

        with patch.dict(postgres_privileges.__opts__, {"test": False}):
            comt = "The privilege(s): {} have been revoked from {}".format("ALL", name)
            ret.update(
                {"comment": comt, "result": True, "changes": {"baruwa": "Absent"}}
            )
            assert (
                postgres_privileges.absent(
                    name, table_name, "table", privileges=["ALL"]
                )
                == ret
            )


def test_absent_group():
    """
    Test absent group
    """
    group_name = "admins"
    name = "baruwa"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    with patch.dict(
        postgres_privileges.__salt__,
        {
            "postgres.has_privileges": mock_true,
            "postgres.privileges_revoke": mock_true,
        },
    ):
        with patch.dict(postgres_privileges.__opts__, {"test": True}):
            comt = "The privilege(s): {} are set to be revoked from {}".format(
                group_name, name
            )
            ret.update({"comment": comt, "result": None})
            assert postgres_privileges.absent(name, group_name, "group") == ret

        with patch.dict(postgres_privileges.__opts__, {"test": False}):
            comt = "The privilege(s): {} have been revoked from {}".format(
                group_name, name
            )
            ret.update(
                {"comment": comt, "result": True, "changes": {"baruwa": "Absent"}}
            )
            assert postgres_privileges.absent(name, group_name, "group") == ret
