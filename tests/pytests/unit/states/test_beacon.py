"""
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
"""

import pytest
import salt.states.beacon as beacon
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {beacon: {}}


def test_present():
    """
    Test to ensure a job is present in the beacon.
    """
    beacon_name = "ps"

    ret = {"name": beacon_name, "changes": {}, "result": False, "comment": ""}

    mock_mod = MagicMock(return_value=ret)
    mock_lst = MagicMock(side_effect=[{beacon_name: {}}, {beacon_name: {}}, {}, {}])
    with patch.dict(
        beacon.__salt__,
        {
            "beacons.list": mock_lst,
            "beacons.modify": mock_mod,
            "beacons.add": mock_mod,
        },
    ):
        assert beacon.present(beacon_name) == ret

        with patch.dict(beacon.__opts__, {"test": False}):
            assert beacon.present(beacon_name) == ret

        with patch.dict(beacon.__opts__, {"test": True}):
            ret.update({"result": True})
            assert beacon.present(beacon_name) == ret


def test_absent():
    """
    Test to ensure a job is absent from the schedule.
    """
    beacon_name = "ps"

    ret = {"name": beacon_name, "changes": {}, "result": False, "comment": ""}

    mock_mod = MagicMock(return_value=ret)
    mock_lst = MagicMock(side_effect=[{beacon_name: {}}, {}])
    with patch.dict(
        beacon.__salt__, {"beacons.list": mock_lst, "beacons.delete": mock_mod}
    ):
        with patch.dict(beacon.__opts__, {"test": False}):
            assert beacon.absent(beacon_name) == ret

        with patch.dict(beacon.__opts__, {"test": True}):
            comt = "ps not configured in beacons"
            ret.update({"comment": comt, "result": True})
            assert beacon.absent(beacon_name) == ret
