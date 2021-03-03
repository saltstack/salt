"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.ntp as ntp
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {ntp: {}}


def test_managed():
    """
    Test to manage NTP servers.
    """
    name = "coffee-script"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_lst = MagicMock(return_value=[])
    with patch.dict(
        ntp.__salt__, {"ntp.get_servers": mock_lst, "ntp.set_servers": mock_lst}
    ):
        comt = "NTP servers already configured as specified"
        ret.update({"comment": comt, "result": True})
        assert ntp.managed(name, []) == ret

        with patch.dict(ntp.__opts__, {"test": True}):
            comt = "NTP servers will be updated to: coffee-script"
            ret.update({"comment": comt, "result": None})
            assert ntp.managed(name, [name]) == ret

        with patch.dict(ntp.__opts__, {"test": False}):
            comt = "Failed to update NTP servers"
            ret.update({"comment": comt, "result": False})
            assert ntp.managed(name, [name]) == ret
