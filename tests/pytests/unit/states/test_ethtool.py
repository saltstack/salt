import pytest

import salt.states.ethtool as ethtool
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        ethtool: {
            "__opts__": {"test": False},
            "__salt__": {},
        }
    }


def test_ethtool_pause():
    expected = {
        "changes": {},
        "comment": "Network device eth0 pause parameters are up to date.",
        "name": "eth0",
        "result": True,
    }
    show_ret = {
        "Autonegotiate": True,
        "RX": True,
        "RX negotiated": False,
        "TX": True,
        "TX negotiated": False,
    }
    mock_show = MagicMock(return_value=show_ret)
    mock_set = MagicMock(return_value=True)
    with patch.dict(
        ethtool.__salt__,
        {"ethtool.set_pause": mock_set, "ethtool.show_pause": mock_show},
    ):
        # clean
        ret = ethtool.pause("eth0", autoneg=True, rx=True, tx=True)
        assert ret == expected

        # changes
        expected["changes"] = {"ethtool_pause": "autoneg: off\nrx: off\ntx: off"}
        expected["comment"] = "Device eth0 pause parameters updated."
        ret = ethtool.pause("eth0", autoneg=False, rx=False, tx=False)
        assert ret == expected
        mock_set.assert_called_once_with("eth0", autoneg=False, rx=False, tx=False)

        # changes, test mode
        mock_set.reset_mock()
        with patch.dict(ethtool.__opts__, {"test": True}):
            expected["result"] = None
            expected["changes"] = {}
            expected[
                "comment"
            ] = "Device eth0 pause parameters are set to be updated:\nautoneg: off\nrx: off\ntx: off"
            ret = ethtool.pause("eth0", autoneg=False, rx=False, tx=False)
            assert ret == expected
            mock_set.assert_not_called()

    # exceptions
    with patch.dict(
        ethtool.__salt__,
        {
            "ethtool.set_pause": MagicMock(side_effect=CommandExecutionError("blargh")),
            "ethtool.show_pause": MagicMock(
                side_effect=[CommandExecutionError, show_ret]
            ),
        },
    ):
        expected["comment"] = "Device eth0 pause parameters are not supported"
        expected["result"] = False
        ret = ethtool.pause("eth0", autoneg=False, rx=False, tx=False)
        assert ret == expected
        ret = ethtool.pause("eth0", autoneg=False, rx=False, tx=False)
        expected["comment"] = "blargh"
        assert ret == expected
