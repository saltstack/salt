from textwrap import dedent

import pytest

import salt.modules.ethtool as ethtool
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        ethtool: {
            "__salt__": {},
        }
    }


@pytest.fixture(scope="module")
def pause_ret():
    cmdret = dedent(
        """Pause parameters for eth0:
        Autonegotiate:  on
        RX:             on
        TX:             on
        RX negotiated:  off
        TX negotiated:  off"""
    )
    return cmdret


@pytest.fixture(scope="module")
def features_ret():
    cmdret = dedent(
        """Features for eth0:
        rx-checksumming: on [fixed]
        tx-checksumming: on
                tx-checksum-ipv4: off [fixed]
                tx-checksum-ip-generic: on
                tx-checksum-ipv6: off [fixed]
                tx-checksum-fcoe-crc: off [fixed]
                tx-checksum-sctp: off [fixed]
        scatter-gather: on
                tx-scatter-gather: on
                tx-scatter-gather-fraglist: off [fixed]
        tcp-segmentation-offload: on
                tx-tcp-segmentation: on
                tx-tcp-ecn-segmentation: on
                tx-tcp-mangleid-segmentation: off
                tx-tcp6-segmentation: on
        udp-fragmentation-offload: off
        generic-segmentation-offload: on
        generic-receive-offload: on
        large-receive-offload: off [fixed]
        rx-vlan-offload: off [fixed]
        tx-vlan-offload: off [fixed]
        ntuple-filters: off [fixed]
        receive-hashing: off [fixed]
        highdma: on [fixed]
        rx-vlan-filter: on [fixed]
        vlan-challenged: off [fixed]
        tx-lockless: off [fixed]
        netns-local: off [fixed]
        tx-gso-robust: on [fixed]
        tx-fcoe-segmentation: off [fixed]
        tx-gre-segmentation: off [fixed]
        tx-gre-csum-segmentation: off [fixed]
        tx-ipxip4-segmentation: off [fixed]
        tx-ipxip6-segmentation: off [fixed]
        tx-udp_tnl-segmentation: off [fixed]
        tx-udp_tnl-csum-segmentation: off [fixed]
        tx-gso-partial: off [fixed]
        tx-sctp-segmentation: off [fixed]
        tx-esp-segmentation: off [fixed]
        tx-udp-segmentation: off [fixed]
        fcoe-mtu: off [fixed]
        tx-nocache-copy: off
        loopback: off [fixed]
        rx-fcs: off [fixed]
        rx-all: off [fixed]
        tx-vlan-stag-hw-insert: off [fixed]
        rx-vlan-stag-hw-parse: off [fixed]
        rx-vlan-stag-filter: off [fixed]
        l2-fwd-offload: off [fixed]
        hw-tc-offload: off [fixed]
        esp-hw-offload: off [fixed]
        esp-tx-csum-hw-offload: off [fixed]
        rx-udp_tunnel-port-offload: off [fixed]
        tls-hw-tx-offload: off [fixed]
        tls-hw-rx-offload: off [fixed]
        rx-gro-hw: off [fixed]
        tls-hw-record: off [fixed]"""
    )
    return cmdret


def test_ethtool__ethtool_command_which_fail():
    with patch("salt.utils.path.which", MagicMock(return_value=None)):
        with pytest.raises(CommandExecutionError):
            ethtool._ethtool_command("eth0")


def test_ethtool__ethtool_command_operation_not_supported():
    mock_cmd_run = MagicMock(
        side_effect=[
            "Pause parameters for eth0:\nCannot get device pause settings: Operation not supported",
            "Cannot get device pause settings: Operation not supported",
        ]
    )
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/ethtool")
    ), patch.dict(ethtool.__salt__, {"cmd.run": mock_cmd_run}):
        with pytest.raises(CommandExecutionError):
            ethtool._ethtool_command("eth0", "-a")
            ethtool._ethtool_command("eth0", "-A", autoneg="off", rx="off", tx="off")


def test_ethtool__ethtool_command(pause_ret):
    mock_cmd_run = MagicMock(return_value=pause_ret)

    with patch(
        "salt.utils.path.which", MagicMock(return_value="/sbin/ethtool")
    ), patch.dict(ethtool.__salt__, {"cmd.run": mock_cmd_run}):
        ret = ethtool._ethtool_command("eth0", "-A", autoneg="off", rx="off", tx="off")

    mock_cmd_run.assert_called_once_with(
        "/sbin/ethtool -A eth0 autoneg off rx off tx off", ignore_retcode=True
    )
    assert pause_ret.splitlines() == ret


def test_ethtool__validate_params():
    with pytest.raises(CommandExecutionError):
        ethtool._validate_params(["not_found"], {"eth": "tool"})
    assert ethtool._validate_params(["eth"], {"eth": "tool"}) == {"eth": "tool"}
    assert ethtool._validate_params(["eth", "not_found"], {"eth": "tool"}) == {
        "eth": "tool"
    }
    assert ethtool._validate_params(["eth", "salt"], {"eth": True, "salt": False}) == {
        "eth": "on",
        "salt": "off",
    }


def test_ethtool_show_pause(pause_ret):
    expected = {
        "Autonegotiate": True,
        "RX": True,
        "RX negotiated": False,
        "TX": True,
        "TX negotiated": False,
    }

    with patch(
        "salt.modules.ethtool._ethtool_command",
        MagicMock(return_value=pause_ret.splitlines()),
    ):
        ret = ethtool.show_pause("eth0")

    assert expected == ret


def test_ethtool_show_features(features_ret):
    expected = {
        "esp-hw-offload": {"fixed": True, "on": False},
        "esp-tx-csum-hw-offload": {"fixed": True, "on": False},
        "fcoe-mtu": {"fixed": True, "on": False},
        "generic-receive-offload": {"fixed": False, "on": True},
        "generic-segmentation-offload": {"fixed": False, "on": True},
        "highdma": {"fixed": True, "on": True},
        "hw-tc-offload": {"fixed": True, "on": False},
        "l2-fwd-offload": {"fixed": True, "on": False},
        "large-receive-offload": {"fixed": True, "on": False},
        "loopback": {"fixed": True, "on": False},
        "netns-local": {"fixed": True, "on": False},
        "ntuple-filters": {"fixed": True, "on": False},
        "receive-hashing": {"fixed": True, "on": False},
        "rx-all": {"fixed": True, "on": False},
        "rx-checksumming": {"fixed": True, "on": True},
        "rx-fcs": {"fixed": True, "on": False},
        "rx-gro-hw": {"fixed": True, "on": False},
        "rx-udp_tunnel-port-offload": {"fixed": True, "on": False},
        "rx-vlan-filter": {"fixed": True, "on": True},
        "rx-vlan-offload": {"fixed": True, "on": False},
        "rx-vlan-stag-filter": {"fixed": True, "on": False},
        "rx-vlan-stag-hw-parse": {"fixed": True, "on": False},
        "scatter-gather": {"fixed": False, "on": True},
        "tcp-segmentation-offload": {"fixed": False, "on": True},
        "tls-hw-record": {"fixed": True, "on": False},
        "tls-hw-rx-offload": {"fixed": True, "on": False},
        "tls-hw-tx-offload": {"fixed": True, "on": False},
        "tx-checksum-fcoe-crc": {"fixed": True, "on": False},
        "tx-checksum-ip-generic": {"fixed": False, "on": True},
        "tx-checksum-ipv4": {"fixed": True, "on": False},
        "tx-checksum-ipv6": {"fixed": True, "on": False},
        "tx-checksum-sctp": {"fixed": True, "on": False},
        "tx-checksumming": {"fixed": False, "on": True},
        "tx-esp-segmentation": {"fixed": True, "on": False},
        "tx-fcoe-segmentation": {"fixed": True, "on": False},
        "tx-gre-csum-segmentation": {"fixed": True, "on": False},
        "tx-gre-segmentation": {"fixed": True, "on": False},
        "tx-gso-partial": {"fixed": True, "on": False},
        "tx-gso-robust": {"fixed": True, "on": True},
        "tx-ipxip4-segmentation": {"fixed": True, "on": False},
        "tx-ipxip6-segmentation": {"fixed": True, "on": False},
        "tx-lockless": {"fixed": True, "on": False},
        "tx-nocache-copy": {"fixed": False, "on": False},
        "tx-scatter-gather": {"fixed": False, "on": True},
        "tx-scatter-gather-fraglist": {"fixed": True, "on": False},
        "tx-sctp-segmentation": {"fixed": True, "on": False},
        "tx-tcp-ecn-segmentation": {"fixed": False, "on": True},
        "tx-tcp-mangleid-segmentation": {"fixed": False, "on": False},
        "tx-tcp-segmentation": {"fixed": False, "on": True},
        "tx-tcp6-segmentation": {"fixed": False, "on": True},
        "tx-udp-segmentation": {"fixed": True, "on": False},
        "tx-udp_tnl-csum-segmentation": {"fixed": True, "on": False},
        "tx-udp_tnl-segmentation": {"fixed": True, "on": False},
        "tx-vlan-offload": {"fixed": True, "on": False},
        "tx-vlan-stag-hw-insert": {"fixed": True, "on": False},
        "udp-fragmentation-offload": {"fixed": False, "on": False},
        "vlan-challenged": {"fixed": True, "on": False},
    }

    with patch(
        "salt.modules.ethtool._ethtool_command",
        MagicMock(return_value=features_ret.splitlines()),
    ):
        ret = ethtool.show_features("eth0")

    assert expected == ret


def test_ethtool_set_pause():
    with patch("salt.modules.ethtool._ethtool_command", MagicMock(return_value="")):
        with pytest.raises(CommandExecutionError):
            ethtool.set_pause("eth0", not_there=False)
        ret = ethtool.set_pause("eth0", autoneg=False)

    assert ret is True


def test_ethtool_set_feature():
    with patch("salt.modules.ethtool._ethtool_command", MagicMock(return_value="")):
        with pytest.raises(CommandExecutionError):
            ethtool.set_feature("eth0", not_there=False)
        ret = ethtool.set_feature("eth0", sg=False)

    assert ret is True
