"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import pytest

import salt.states.kmod as kmod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {kmod: {}}


def test_present():
    """
    Test to ensure that the specified kernel module is loaded.
    """
    name = "cheese"
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock_mod_list = MagicMock(return_value=[name])
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        comment = "Kernel module {} is already present".format(name)
        ret.update({"comment": comment})
        assert kmod.present(name) == ret

    mock_mod_list = MagicMock(return_value=[])
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        with patch.dict(kmod.__opts__, {"test": True}):
            comment = "Kernel module {} is set to be loaded".format(name)
            ret.update({"comment": comment, "result": None})
            assert kmod.present(name) == ret

    mock_mod_list = MagicMock(return_value=[])
    mock_available = MagicMock(return_value=[name])
    mock_load = MagicMock(return_value=[name])
    with patch.dict(
        kmod.__salt__,
        {
            "kmod.mod_list": mock_mod_list,
            "kmod.available": mock_available,
            "kmod.load": mock_load,
        },
    ):
        with patch.dict(kmod.__opts__, {"test": False}):
            comment = "Loaded kernel module {}".format(name)
            ret.update(
                {"comment": comment, "result": True, "changes": {name: "loaded"}}
            )
            assert kmod.present(name) == ret


def test_present_multi():
    """
    Test to ensure that multiple kernel modules are loaded.
    """
    name = "salted kernel"
    mods = ["cheese", "crackers"]
    ret = {"name": name, "result": True, "changes": {}}

    mock_mod_list = MagicMock(return_value=mods)
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        call_ret = kmod.present(name, mods=mods)

        # Check comment independently: makes test more stable on PY3
        comment = call_ret.pop("comment")
        assert "cheese" in comment
        assert "crackers" in comment
        assert "are already present" in comment

        # Assert against all other dictionary key/values
        assert ret == call_ret

    mock_mod_list = MagicMock(return_value=[])
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        with patch.dict(kmod.__opts__, {"test": True}):
            call_ret = kmod.present(name, mods=mods)
            ret.update({"result": None})

            # Check comment independently: makes test more stable on PY3
            comment = call_ret.pop("comment")
            assert "cheese" in comment
            assert "crackers" in comment
            assert "are set to be loaded" in comment

            # Assert against all other dictionary key/values
            assert ret == call_ret

    mock_mod_list = MagicMock(return_value=[])
    mock_available = MagicMock(return_value=mods)
    mock_load = MagicMock(return_value=mods)
    with patch.dict(
        kmod.__salt__,
        {
            "kmod.mod_list": mock_mod_list,
            "kmod.available": mock_available,
            "kmod.load": mock_load,
        },
    ):
        with patch.dict(kmod.__opts__, {"test": False}):
            call_ret = kmod.present(name, mods=mods)
            ret.update(
                {"result": True, "changes": {mods[0]: "loaded", mods[1]: "loaded"}}
            )

            # Check comment independently: makes test more stable on PY3
            comment = call_ret.pop("comment")
            assert "cheese" in comment
            assert "crackers" in comment
            assert "Loaded kernel modules" in comment

            # Assert against all other dictionary key/values
            assert ret == call_ret


def test_absent():
    """
    Test to verify that the named kernel module is not loaded.
    """
    name = "cheese"
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock_mod_list = MagicMock(return_value=[name])
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        with patch.dict(kmod.__opts__, {"test": True}):
            comment = "Kernel module {} is set to be removed".format(name)
            ret.update({"comment": comment, "result": None})
            assert kmod.absent(name) == ret

    mock_mod_list = MagicMock(return_value=[name])
    mock_remove = MagicMock(return_value=[name])
    with patch.dict(
        kmod.__salt__, {"kmod.mod_list": mock_mod_list, "kmod.remove": mock_remove}
    ):
        with patch.dict(kmod.__opts__, {"test": False}):
            comment = "Removed kernel module {}".format(name)
            ret.update(
                {"comment": comment, "result": True, "changes": {name: "removed"}}
            )
            assert kmod.absent(name) == ret

    mock_mod_list = MagicMock(return_value=[])
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        with patch.dict(kmod.__opts__, {"test": True}):
            comment = "Kernel module {} is already removed".format(name)
            ret.update({"comment": comment, "result": True, "changes": {}})
            assert kmod.absent(name) == ret


def test_absent_multi():
    """
    Test to verify that multiple kernel modules are not loaded.
    """
    name = "salted kernel"
    mods = ["cheese", "crackers"]
    ret = {"name": name, "result": True, "changes": {}}

    mock_mod_list = MagicMock(return_value=mods)
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        with patch.dict(kmod.__opts__, {"test": True}):
            ret.update({"result": None})
            call_ret = kmod.absent(name, mods=mods)

            # Check comment independently: makes test more stable on PY3
            comment = call_ret.pop("comment")
            assert "cheese" in comment
            assert "crackers" in comment
            assert "are set to be removed" in comment

            # Assert against all other dictionary key/values
            assert ret == call_ret

    mock_mod_list = MagicMock(return_value=mods)
    mock_remove = MagicMock(return_value=mods)
    with patch.dict(
        kmod.__salt__, {"kmod.mod_list": mock_mod_list, "kmod.remove": mock_remove}
    ):
        with patch.dict(kmod.__opts__, {"test": False}):
            call_ret = kmod.absent(name, mods=mods)
            ret.update(
                {"result": True, "changes": {mods[0]: "removed", mods[1]: "removed"}}
            )

            # Check comment independently: makes test more stable on PY3
            comment = call_ret.pop("comment")
            assert "cheese" in comment
            assert "crackers" in comment
            assert "Removed kernel modules" in comment

            # Assert against all other dictionary key/values
            assert ret == call_ret

    mock_mod_list = MagicMock(return_value=[])
    with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
        with patch.dict(kmod.__opts__, {"test": True}):
            comment = "Kernel modules {} are already removed".format(", ".join(mods))
            ret.update({"comment": comment, "result": True, "changes": {}})
            assert kmod.absent(name, mods=mods) == ret
