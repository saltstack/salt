import pytest

import salt.states.openvswitch_port as openvswitch_port
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {openvswitch_port: {"__opts__": {"test": False}}}


def test_present():
    """
    Test to verify that the named port exists on bridge, eventually creates it.
    """
    name = "salt"
    bridge = "br-salt"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(return_value=True)
    mock_l = MagicMock(return_value=["salt"])
    mock_n = MagicMock(return_value=[])

    with patch.dict(
        openvswitch_port.__salt__,
        {
            "openvswitch.bridge_exists": mock,
            "openvswitch.interface_get_type": MagicMock(return_value='""'),
            "openvswitch.port_list": mock_l,
        },
    ):
        comt = "Port salt already exists."
        ret.update({"comment": comt, "result": True})
        assert openvswitch_port.present(name, bridge) == ret

    with patch.dict(
        openvswitch_port.__salt__,
        {
            "openvswitch.bridge_exists": mock,
            "openvswitch.interface_get_type": MagicMock(return_value='""'),
            "openvswitch.port_list": mock_n,
            "openvswitch.port_add": mock,
        },
    ):
        comt = "Port salt created on bridge br-salt."
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    "salt": {
                        "new": "Created port salt on bridge br-salt.",
                        "old": "No port named salt present.",
                    },
                },
            }
        )
        assert openvswitch_port.present(name, bridge) == ret
    with patch.dict(
        openvswitch_port.__salt__,
        {
            "openvswitch.bridge_exists": mock,
            "openvswitch.port_list": mock_n,
            "openvswitch.port_add": mock,
            "openvswitch.interface_get_options": mock_n,
            "openvswitch.interface_get_type": MagicMock(return_value=""),
            "openvswitch.port_create_gre": mock,
            "dig.check_ip": mock,
        },
    ):
        comt = "Port salt created on bridge br-salt."
        ret.update(
            {
                "result": True,
                "comment": (
                    "Created GRE tunnel interface salt with remote ip 10.0.0.1  and key"
                    " 1 on bridge br-salt."
                ),
                "changes": {
                    "salt": {
                        "new": (
                            "Created GRE tunnel interface salt with remote ip 10.0.0.1"
                            " and key 1 on bridge br-salt."
                        ),
                        "old": (
                            "No GRE tunnel interface salt with remote ip 10.0.0.1 and"
                            " key 1 on bridge br-salt present."
                        ),
                    },
                },
            }
        )
        assert (
            openvswitch_port.present(
                name, bridge, tunnel_type="gre", id=1, remote="10.0.0.1"
            )
            == ret
        )
