"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.rdp as rdp
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rdp: {}}


def test_enabled():
    """
    Test to enable the RDP service and make sure access
    to the RDP port is allowed in the firewall configuration.
    """
    name = "my_service"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_t = MagicMock(side_effect=[False, False, True])
    mock_f = MagicMock(return_value=False)
    with patch.dict(rdp.__salt__, {"rdp.status": mock_t, "rdp.enable": mock_f}):
        with patch.dict(rdp.__opts__, {"test": True}):
            comt = "RDP will be enabled"
            ret.update({"comment": comt, "result": None})
            assert rdp.enabled(name) == ret

        with patch.dict(rdp.__opts__, {"test": False}):
            ret.update(
                {"comment": "", "result": False, "changes": {"RDP was enabled": True}}
            )
            assert rdp.enabled(name) == ret

            comt = "RDP is enabled"
            ret.update({"comment": comt, "result": True, "changes": {}})
            assert rdp.enabled(name) == ret


def test_disabled():
    """
    Test to disable the RDP service.
    """
    name = "my_service"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[True, True, False])
    mock_t = MagicMock(return_value=True)
    with patch.dict(rdp.__salt__, {"rdp.status": mock, "rdp.disable": mock_t}):
        with patch.dict(rdp.__opts__, {"test": True}):
            comt = "RDP will be disabled"
            ret.update({"comment": comt, "result": None})
            assert rdp.disabled(name) == ret

        with patch.dict(rdp.__opts__, {"test": False}):
            ret.update(
                {"comment": "", "result": True, "changes": {"RDP was disabled": True}}
            )
            assert rdp.disabled(name) == ret

            comt = "RDP is disabled"
            ret.update({"comment": comt, "result": True, "changes": {}})
            assert rdp.disabled(name) == ret
