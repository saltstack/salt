import salt.states.virt as virt
from tests.support.mock import MagicMock, patch

from .test_helpers import network_update_call


def test_network_defined_not_existing(test):
    """
    network_defined state tests if the network doesn't exist yet.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        define_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.network_info": MagicMock(
                    side_effect=[{}, {"mynet": {"active": False}}]
                ),
                "virt.network_define": define_mock,
            },
        ):
            assert virt.network_defined(
                "mynet",
                "br2",
                "bridge",
                vport="openvswitch",
                tag=180,
                ipv4_config={
                    "cidr": "192.168.2.0/24",
                    "dhcp_ranges": [
                        {"start": "192.168.2.10", "end": "192.168.2.25"},
                        {"start": "192.168.2.110", "end": "192.168.2.125"},
                    ],
                },
                ipv6_config={
                    "cidr": "2001:db8:ca2:2::1/64",
                    "dhcp_ranges": [
                        {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                    ],
                },
                mtu=9000,
                domain={"name": "acme.lab"},
                nat={"ports": {"start": 1024, "end": 2048}},
                interfaces="eth0 eth1",
                addresses="0000:01:02.4 0000:01:02.5",
                physical_function="eth4",
                dns={
                    "hosts": {
                        "192.168.2.10": {"name": "web", "mac": "de:ad:be:ef:00:00"}
                    }
                },
                autostart=False,
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "mynet",
                "changes": {"mynet": "Network defined"},
                "result": None if test else True,
                "comment": "Network mynet defined",
            }
            if not test:
                define_mock.assert_called_with(
                    "mynet",
                    "br2",
                    "bridge",
                    vport="openvswitch",
                    tag=180,
                    autostart=False,
                    start=False,
                    ipv4_config={
                        "cidr": "192.168.2.0/24",
                        "dhcp_ranges": [
                            {"start": "192.168.2.10", "end": "192.168.2.25"},
                            {"start": "192.168.2.110", "end": "192.168.2.125"},
                        ],
                    },
                    ipv6_config={
                        "cidr": "2001:db8:ca2:2::1/64",
                        "dhcp_ranges": [
                            {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                        ],
                    },
                    mtu=9000,
                    domain={"name": "acme.lab"},
                    nat={"ports": {"start": 1024, "end": 2048}},
                    interfaces="eth0 eth1",
                    addresses="0000:01:02.4 0000:01:02.5",
                    physical_function="eth4",
                    dns={
                        "hosts": {
                            "192.168.2.10": {"name": "web", "mac": "de:ad:be:ef:00:00"}
                        }
                    },
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
            else:
                define_mock.assert_not_called()


def test_network_defined_no_change(test):
    """
    network_defined state tests if the network doesn't need update.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        define_mock = MagicMock(return_value=True)
        update_mock = MagicMock(return_value=False)
        with patch.dict(
            virt.__salt__,
            {
                "virt.network_info": MagicMock(
                    return_value={"mynet": {"active": True, "autostart": True}}
                ),
                "virt.network_define": define_mock,
                "virt.network_update": update_mock,
            },
        ):
            assert virt.network_defined("mynet", "br2", "bridge") == {
                "name": "mynet",
                "changes": {},
                "result": True,
                "comment": "Network mynet unchanged",
            }
            define_mock.assert_not_called()
            assert update_mock.call_args_list == [
                network_update_call("mynet", "br2", "bridge", test=True)
            ]


def test_network_defined_change(test):
    """
    network_defined state tests if the network needs update.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        define_mock = MagicMock(return_value=True)
        update_mock = MagicMock(return_value=True)
        autostart_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.network_info": MagicMock(
                    return_value={"mynet": {"active": True, "autostart": True}}
                ),
                "virt.network_define": define_mock,
                "virt.network_update": update_mock,
                "virt.network_set_autostart": autostart_mock,
            },
        ):
            assert virt.network_defined(
                "mynet",
                "br2",
                "bridge",
                vport="openvswitch",
                tag=180,
                ipv4_config={
                    "cidr": "192.168.2.0/24",
                    "dhcp_ranges": [
                        {"start": "192.168.2.10", "end": "192.168.2.25"},
                        {"start": "192.168.2.110", "end": "192.168.2.125"},
                    ],
                },
                ipv6_config={
                    "cidr": "2001:db8:ca2:2::1/64",
                    "dhcp_ranges": [
                        {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                    ],
                },
                mtu=9000,
                domain={"name": "acme.lab"},
                nat={"ports": {"start": 1024, "end": 2048}},
                interfaces="eth0 eth1",
                addresses="0000:01:02.4 0000:01:02.5",
                physical_function="eth4",
                dns={
                    "hosts": {
                        "192.168.2.10": {"name": "web", "mac": "de:ad:be:ef:00:00"}
                    }
                },
                autostart=False,
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "mynet",
                "changes": {"mynet": "Network updated, autostart flag changed"},
                "result": None if test else True,
                "comment": "Network mynet updated, autostart flag changed",
            }
            define_mock.assert_not_called()
            expected_update_kwargs = {
                "vport": "openvswitch",
                "tag": 180,
                "ipv4_config": {
                    "cidr": "192.168.2.0/24",
                    "dhcp_ranges": [
                        {"start": "192.168.2.10", "end": "192.168.2.25"},
                        {"start": "192.168.2.110", "end": "192.168.2.125"},
                    ],
                },
                "ipv6_config": {
                    "cidr": "2001:db8:ca2:2::1/64",
                    "dhcp_ranges": [
                        {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                    ],
                },
                "mtu": 9000,
                "domain": {"name": "acme.lab"},
                "nat": {"ports": {"start": 1024, "end": 2048}},
                "interfaces": "eth0 eth1",
                "addresses": "0000:01:02.4 0000:01:02.5",
                "physical_function": "eth4",
                "dns": {
                    "hosts": {
                        "192.168.2.10": {"name": "web", "mac": "de:ad:be:ef:00:00"}
                    }
                },
                "connection": "myconnection",
                "username": "user",
                "password": "secret",
            }
            calls = [
                network_update_call(
                    "mynet", "br2", "bridge", **expected_update_kwargs, test=True
                )
            ]
            if test:
                assert update_mock.call_args_list == calls
                autostart_mock.assert_not_called()
            else:
                calls.append(
                    network_update_call(
                        "mynet", "br2", "bridge", **expected_update_kwargs, test=False
                    )
                )
                assert update_mock.call_args_list == calls
                autostart_mock.assert_called_with(
                    "mynet",
                    state="off",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )


def test_network_defined_error(test):
    """
    network_defined state tests if an error is triggered by libvirt.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        define_mock = MagicMock(return_value=True)
        with patch.dict(
            virt.__salt__,
            {
                "virt.network_info": MagicMock(
                    side_effect=virt.libvirt.libvirtError("Some error")
                )
            },
        ):
            assert virt.network_defined("mynet", "br2", "bridge") == {
                "name": "mynet",
                "changes": {},
                "result": False,
                "comment": "Some error",
            }
            define_mock.assert_not_called()


def test_network_running_not_existing(test):
    """
    network_running state test cases, non-existing network case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        define_mock = MagicMock(return_value=True)
        start_mock = MagicMock(return_value=True)
        # Non-existing network case
        with patch.dict(
            virt.__salt__,
            {
                "virt.network_info": MagicMock(
                    side_effect=[{}, {"mynet": {"active": False}}]
                ),
                "virt.network_define": define_mock,
                "virt.network_start": start_mock,
            },
        ):
            assert virt.network_running(
                "mynet",
                "br2",
                "bridge",
                vport="openvswitch",
                tag=180,
                ipv4_config={
                    "cidr": "192.168.2.0/24",
                    "dhcp_ranges": [
                        {"start": "192.168.2.10", "end": "192.168.2.25"},
                        {"start": "192.168.2.110", "end": "192.168.2.125"},
                    ],
                },
                ipv6_config={
                    "cidr": "2001:db8:ca2:2::1/64",
                    "dhcp_ranges": [
                        {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                    ],
                },
                mtu=9000,
                domain={"name": "acme.lab"},
                nat={"ports": {"start": 1024, "end": 2048}},
                interfaces="eth0 eth1",
                addresses="0000:01:02.4 0000:01:02.5",
                physical_function="eth4",
                dns={
                    "hosts": {
                        "192.168.2.10": {"name": "web", "mac": "de:ad:be:ef:00:00"}
                    }
                },
                autostart=False,
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "mynet",
                "changes": {"mynet": "Network defined and started"},
                "comment": "Network mynet defined and started",
                "result": None if test else True,
            }
            if not test:
                define_mock.assert_called_with(
                    "mynet",
                    "br2",
                    "bridge",
                    vport="openvswitch",
                    tag=180,
                    autostart=False,
                    start=False,
                    ipv4_config={
                        "cidr": "192.168.2.0/24",
                        "dhcp_ranges": [
                            {"start": "192.168.2.10", "end": "192.168.2.25"},
                            {"start": "192.168.2.110", "end": "192.168.2.125"},
                        ],
                    },
                    ipv6_config={
                        "cidr": "2001:db8:ca2:2::1/64",
                        "dhcp_ranges": [
                            {"start": "2001:db8:ca2:1::10", "end": "2001:db8:ca2::1f"},
                        ],
                    },
                    mtu=9000,
                    domain={"name": "acme.lab"},
                    nat={"ports": {"start": 1024, "end": 2048}},
                    interfaces="eth0 eth1",
                    addresses="0000:01:02.4 0000:01:02.5",
                    physical_function="eth4",
                    dns={
                        "hosts": {
                            "192.168.2.10": {"name": "web", "mac": "de:ad:be:ef:00:00"}
                        }
                    },
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
                start_mock.assert_called_with(
                    "mynet",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
            else:
                define_mock.assert_not_called()
                start_mock.assert_not_called()


def test_network_running_nochange(test):
    """
    network_running state test cases, no change case case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        define_mock = MagicMock(return_value=True)
        update_mock = MagicMock(return_value=False)
        with patch.dict(
            virt.__salt__,
            {
                "virt.network_info": MagicMock(
                    return_value={"mynet": {"active": True, "autostart": True}}
                ),
                "virt.network_define": define_mock,
                "virt.network_update": update_mock,
            },
        ):
            assert virt.network_running("mynet", "br2", "bridge") == {
                "name": "mynet",
                "changes": {},
                "comment": "Network mynet unchanged and is running",
                "result": None if test else True,
            }
            assert update_mock.call_args_list == [
                network_update_call("mynet", "br2", "bridge", test=True)
            ]


def test_network_running_stopped(test):
    """
    network_running state test cases, network stopped case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        define_mock = MagicMock(return_value=True)
        start_mock = MagicMock(return_value=True)
        update_mock = MagicMock(return_value=False)
        with patch.dict(
            virt.__salt__,
            {  # pylint: disable=no-member
                "virt.network_info": MagicMock(
                    return_value={"mynet": {"active": False, "autostart": True}}
                ),
                "virt.network_start": start_mock,
                "virt.network_define": define_mock,
                "virt.network_update": update_mock,
            },
        ):
            assert virt.network_running(
                "mynet",
                "br2",
                "bridge",
                connection="myconnection",
                username="user",
                password="secret",
            ) == {
                "name": "mynet",
                "changes": {"mynet": "Network started"},
                "comment": "Network mynet unchanged and started",
                "result": None if test else True,
            }
            assert update_mock.call_args_list == [
                network_update_call(
                    "mynet",
                    "br2",
                    "bridge",
                    connection="myconnection",
                    username="user",
                    password="secret",
                    test=True,
                )
            ]
            if not test:
                start_mock.assert_called_with(
                    "mynet",
                    connection="myconnection",
                    username="user",
                    password="secret",
                )
            else:
                start_mock.assert_not_called()


def test_network_running_error(test):
    """
    network_running state test cases, libvirt error case.
    """
    with patch.dict(virt.__opts__, {"test": test}):
        with patch.dict(
            virt.__salt__,
            {
                "virt.network_info": MagicMock(
                    side_effect=virt.libvirt.libvirtError("Some error")
                ),
            },
        ):
            assert virt.network_running("mynet", "br2", "bridge") == {
                "name": "mynet",
                "changes": {},
                "comment": "Some error",
                "result": False,
            }
