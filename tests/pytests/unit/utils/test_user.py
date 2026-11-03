from types import SimpleNamespace

import pytest

from tests.support.mock import MagicMock, patch

pytest.importorskip("grp")

import grp

import salt.utils.user


def test_get_group_name():
    """
    get_group_name returns the group name for a known gid.
    """
    with patch(
        "grp.getgrgid", MagicMock(return_value=SimpleNamespace(gr_name="wheel"))
    ):
        assert salt.utils.user.get_group_name(0) == "wheel"


def test_get_group_name_unknown_gid():
    """
    get_group_name returns None when the gid does not exist.
    """
    with patch("grp.getgrgid", MagicMock(side_effect=KeyError(9999))):
        assert salt.utils.user.get_group_name(9999) is None


def test_get_group_list():
    getpwname = SimpleNamespace(pw_gid=1000)
    getgrgid = MagicMock(side_effect=[SimpleNamespace(gr_name="remote")])
    group_lines = [
        ["games", "x", 50, []],
        ["salt", "x", 1000, []],
    ]
    getgrall = [grp.struct_group(comps) for comps in group_lines]
    with patch("os.getgrouplist", MagicMock(return_value=[50, 1000, 12000])), patch(
        "pwd.getpwnam", MagicMock(return_value=getpwname)
    ), patch("salt.utils.user._getgrall", MagicMock(return_value=getgrall)), patch(
        "grp.getgrgid", getgrgid
    ):
        group_list = salt.utils.user.get_group_list("salt")
        assert group_list == ["games", "remote", "salt"]
        getgrgid.assert_called_once()
