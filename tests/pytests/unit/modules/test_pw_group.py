"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import pytest

import salt.modules.pw_group as pw_group
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pw_group: {"grinfo": {}}}


def test_add():
    """
    Tests to add the specified group
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(pw_group.__salt__, {"cmd.run_all": mock}):
        assert pw_group.add("a")


def test_delete():
    """
    Tests to remove the named group
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(pw_group.__salt__, {"cmd.run_all": mock}):
        assert pw_group.delete("a")


@pytest.mark.skip_on_windows(reason="grp not available on Windows")
def test_info():
    """
    Tests to return information about a group
    """
    assert pw_group.info("name") == {}

    mock = MagicMock(
        return_value={
            "gr_name": "A",
            "gr_passwd": "B",
            "gr_gid": 1,
            "gr_mem": ["C", "D"],
        }
    )
    with patch.dict(pw_group.grinfo, mock):
        assert pw_group.info("name") == {}


@pytest.mark.skip_on_windows(reason="grp not available on Windows")
def test_getent():
    """
    Tests for return info on all groups
    """
    mock_getent = [{"passwd": "x", "gid": 0, "name": "root"}]
    with patch.dict(pw_group.__context__, {"group.getent": mock_getent}):
        assert {"passwd": "x", "gid": 0, "name": "root"} == pw_group.getent()[0]

    mock = MagicMock(return_value="A")
    with patch.object(pw_group, "info", mock):
        assert pw_group.getent(True)[0] == "A"


def test_chgid():
    """
    tests to change the gid for a named group
    """
    mock = MagicMock(return_value=1)
    with patch.dict(pw_group.__salt__, {"file.group_to_gid": mock}):
        assert pw_group.chgid("name", 1)

    mock = MagicMock(side_effect=[1, 0])
    with patch.dict(pw_group.__salt__, {"file.group_to_gid": mock}):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_group.__salt__, {"cmd.run": mock}):
            assert pw_group.chgid("name", 0)

    mock = MagicMock(side_effect=[1, 1])
    with patch.dict(pw_group.__salt__, {"file.group_to_gid": mock}):
        mock = MagicMock(return_value=None)
        with patch.dict(pw_group.__salt__, {"cmd.run": mock}):
            assert not pw_group.chgid("name", 0)
