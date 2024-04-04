import os

import pytest

import salt.modules.kmod as kmod
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {kmod: {}}


def test_available():
    """
    Tests return a list of all available kernel modules
    """
    with patch("salt.modules.kmod.available", MagicMock(return_value=["kvm"])):
        assert ["kvm"] == kmod.available()


def test_check_available():
    """
    Tests if the specified kernel module is available
    """
    with patch("salt.modules.kmod.available", MagicMock(return_value=["kvm"])):
        assert kmod.check_available("kvm") is True


def test_lsmod():
    """
    Tests return information about currently loaded modules
    """
    ret_str = """Module                  Size  Used by
    kvm_intel             233472  0
    """
    expected = [{"size": "233472", "module": "kvm_intel", "depcount": "0", "deps": []}]
    mock_cmd = MagicMock(return_value=ret_str)
    with patch(
        "salt.utils.path.which", MagicMock(side_effect=[None, "/sbin/lsmod"])
    ), patch.dict(kmod.__salt__, {"cmd.run": mock_cmd}):
        with pytest.raises(CommandExecutionError):
            kmod.lsmod()
        assert expected == kmod.lsmod()


@pytest.mark.skipif(
    not os.path.isfile("/etc/modules"), reason="/etc/modules not present"
)
def test_mod_list():
    """
    Tests return a list of the loaded module names
    """
    with patch(
        "salt.modules.kmod._get_modules_conf",
        MagicMock(return_value="/etc/modules"),
    ):
        with patch(
            "salt.modules.kmod._strip_module_name", MagicMock(return_value="lp")
        ):
            assert ["lp"] == kmod.mod_list(True)

    mock_ret = [{"size": 100, "module": None, "depcount": 10, "deps": None}]
    with patch("salt.modules.kmod.lsmod", MagicMock(return_value=mock_ret)):
        assert [None] == kmod.mod_list(False)


def test_load():
    """
    Tests to loads specified kernel module.
    """
    mod = "cheese"
    err_msg = "Module too moldy, refusing to load"
    mock_persist = MagicMock(return_value={mod})
    mock_lsmod = MagicMock(
        return_value=[{"size": 100, "module": None, "depcount": 10, "deps": None}]
    )
    mock_run_all_0 = MagicMock(return_value={"retcode": 0})
    mock_run_all_1 = MagicMock(return_value={"retcode": 1, "stderr": err_msg})

    with patch("salt.modules.kmod._set_persistent_module", mock_persist):
        with patch(
            "salt.utils.path.which",
            MagicMock(side_effect=[None, "/sbin/modprobe", "/sbin/modprobe"]),
        ), patch("salt.modules.kmod.lsmod", mock_lsmod):
            with patch.dict(
                kmod.__salt__, {"cmd.run_all": mock_run_all_0}
            ), pytest.raises(CommandExecutionError):
                kmod.load(mod, True)

            with patch.dict(kmod.__salt__, {"cmd.run_all": mock_run_all_0}):
                assert [mod] == kmod.load(mod, True)

            with patch.dict(kmod.__salt__, {"cmd.run_all": mock_run_all_1}):
                assert f"Error loading module {mod}: {err_msg}" == kmod.load(mod)


def test_is_loaded():
    """
    Tests if specified kernel module is loaded.
    """
    with patch("salt.modules.kmod.mod_list", MagicMock(return_value={"lp"})):
        assert kmod.is_loaded("lp") is True


def test_remove():
    """
    Tests to remove the specified kernel module
    """
    mod = "cheese"
    err_msg = "Cannot find module: it has been eaten"
    mock_persist = MagicMock(return_value={mod})
    mock_lsmod = MagicMock(
        return_value=[{"size": 100, "module": None, "depcount": 10, "deps": None}]
    )
    mock_run_all_0 = MagicMock(return_value={"retcode": 0})
    mock_run_all_1 = MagicMock(return_value={"retcode": 1, "stderr": err_msg})

    with patch("salt.modules.kmod._remove_persistent_module", mock_persist):
        with patch(
            "salt.utils.path.which",
            MagicMock(side_effect=[None, "/sbin/rmmod", "/sbin/rmmod", "/sbin/rmmod"]),
        ), patch("salt.modules.kmod.lsmod", mock_lsmod):
            with patch.dict(kmod.__salt__, {"cmd.run_all": mock_run_all_0}):
                with pytest.raises(CommandExecutionError):
                    kmod.remove(mod)

                assert [mod] == kmod.remove(mod, True)

                assert [] == kmod.remove(mod)

            with patch.dict(kmod.__salt__, {"cmd.run_all": mock_run_all_1}):
                assert "Error removing module {}: {}".format(
                    mod, err_msg
                ) == kmod.remove(mod, True)
