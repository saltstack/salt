"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.serverdensity_device as serverdensity_device
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {serverdensity_device: {}}


def test_monitored():
    """
    Test to device is monitored with Server Density.
    """
    name = "my_special_server"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_dict = MagicMock(return_value={"id": name})
    mock_t = MagicMock(side_effect=[True, {"agentKey": True}, [{"agentKey": True}]])
    mock_sd = MagicMock(side_effect=[["sd-agent"], [], True])
    with patch.multiple(
        serverdensity_device,
        __salt__={
            "status.all_status": mock_dict,
            "grains.items": mock_dict,
            "serverdensity_device.ls": mock_t,
            "pkg.list_pkgs": mock_sd,
            "serverdensity_device.install_agent": mock_sd,
        },
        __opts__={"test": False},
    ):
        comt = (
            "Such server name already exists in this"
            " Server Density account. And sd-agent is installed"
        )
        ret.update({"comment": comt})
        assert serverdensity_device.monitored(name) == ret

        comt = "Successfully installed agent and created device in Server Density db."
        ret.update(
            {
                "comment": comt,
                "changes": {
                    "created_device": {"agentKey": True},
                    "installed_agent": True,
                },
            }
        )
        assert serverdensity_device.monitored(name) == ret
