"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.status as status
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {status: {}}


def test_loadavg():
    """
    Test to return the current load average for the specified minion.
    """
    name = "mymonitor"

    ret = {"name": name, "changes": {}, "result": True, "data": {}, "comment": ""}

    mock = MagicMock(return_value=[])
    with patch.dict(status.__salt__, {"status.loadavg": mock}):
        comt = "Requested load average mymonitor not available "
        ret.update({"comment": comt, "result": False})
        assert status.loadavg(name) == ret

    mock = MagicMock(return_value={name: 3})
    with patch.dict(status.__salt__, {"status.loadavg": mock}):
        comt = "Min must be less than max"
        ret.update({"comment": comt, "result": False})
        assert status.loadavg(name, 1, 5) == ret

        comt = "Load avg is below minimum of 4 at 3.0"
        ret.update({"comment": comt, "data": 3})
        assert status.loadavg(name, 5, 4) == ret

        comt = "Load avg above maximum of 2 at 3.0"
        ret.update({"comment": comt, "data": 3})
        assert status.loadavg(name, 2, 1) == ret

        comt = "Load avg in acceptable range"
        ret.update({"comment": comt, "result": True})
        assert status.loadavg(name, 3, 1) == ret


def test_process():
    """
    Test to return whether the specified signature
    is found in the process tree.
    """
    name = "mymonitor"

    ret = {"name": name, "changes": {}, "result": True, "data": {}, "comment": ""}

    mock = MagicMock(side_effect=[{}, {name: 1}])
    with patch.dict(status.__salt__, {"status.pid": mock}):
        comt = 'Process signature "mymonitor" not found '
        ret.update({"comment": comt, "result": False})
        assert status.process(name) == ret

        comt = 'Process signature "mymonitor" was found '
        ret.update({"comment": comt, "result": True, "data": {name: 1}})
        assert status.process(name) == ret
