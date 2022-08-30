# Copyright 2007 Google Inc.
#  Licensed to PSF under a Contributor Agreement.
#
#

# This is test_ipaddress.py from Python 3.9.5, verbatim, with minor compatility changes
#    https://github.com/python/cpython/blob/v3.9.5/Lib/test/test_ipaddress.py
#
# Modifications:
#  - Switch the ipaddress import to salt._compat
#  - Copy the `LARGEST` and `SMALLEST` implementation, from 3.9.1
#  - Adjust IpaddrUnitTest.testNetworkElementCaching because we're not using cached_property

"""Unittest for ipaddress module."""

# pylint: disable=string-substitution-usage-error,pointless-statement,abstract-method,cell-var-from-loop

import sys

import pytest

from salt._compat import ipaddress

pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


@pytest.fixture
def ipv4_address():
    return ipaddress.IPv4Address("1.2.3.4")


@pytest.fixture
def ipv4_interface():
    return ipaddress.IPv4Interface("1.2.3.4/24")


@pytest.fixture
def ipv4_network():
    return ipaddress.IPv4Network("1.2.3.0/24")


@pytest.fixture
def ipv6_address():
    return ipaddress.IPv6Interface("2001:658:22a:cafe:200:0:0:1")


@pytest.fixture
def ipv6_interface():
    return ipaddress.IPv6Interface("2001:658:22a:cafe:200:0:0:1/64")


@pytest.fixture
def ipv6_network():
    return ipaddress.IPv6Network("2001:658:22a:cafe::/64")


@pytest.fixture
def ipv6_scoped_address():
    return ipaddress.IPv6Interface("2001:658:22a:cafe:200:0:0:1%scope")


@pytest.fixture
def ipv6_scoped_interface():
    return ipaddress.IPv6Interface("2001:658:22a:cafe:200:0:0:1%scope/64")


@pytest.fixture
def ipv6_scoped_network():
    return ipaddress.IPv6Network("2001:658:22a:cafe::%scope/64")


def test_repr():
    assert "IPv4Interface('1.2.3.4/32')" == repr(ipaddress.IPv4Interface("1.2.3.4"))
    assert "IPv6Interface('::1/128')" == repr(ipaddress.IPv6Interface("::1"))
    assert "IPv6Interface('::1%scope/128')" == repr(
        ipaddress.IPv6Interface("::1%scope")
    )


# issue #16531: constructing IPv4Network from an (address, mask) tuple
def test_ipv4_tuple():
    # /32
    ip = ipaddress.IPv4Address("192.0.2.1")
    net = ipaddress.IPv4Network("192.0.2.1/32")
    assert ipaddress.IPv4Network(("192.0.2.1", 32)) == net
    assert ipaddress.IPv4Network((ip, 32)) == net
    assert ipaddress.IPv4Network((3221225985, 32)) == net
    assert ipaddress.IPv4Network(("192.0.2.1", "255.255.255.255")) == net
    assert ipaddress.IPv4Network((ip, "255.255.255.255")) == net
    assert ipaddress.IPv4Network((3221225985, "255.255.255.255")) == net
    # strict=True and host bits set
    pytest.raises(ValueError, ipaddress.IPv4Network, ("192.0.2.1", 24))
    pytest.raises(ValueError, ipaddress.IPv4Network, (ip, 24))
    pytest.raises(ValueError, ipaddress.IPv4Network, (3221225985, 24))
    pytest.raises(ValueError, ipaddress.IPv4Network, ("192.0.2.1", "255.255.255.0"))
    pytest.raises(ValueError, ipaddress.IPv4Network, (ip, "255.255.255.0"))
    pytest.raises(ValueError, ipaddress.IPv4Network, (3221225985, "255.255.255.0"))
    # strict=False and host bits set
    net = ipaddress.IPv4Network("192.0.2.0/24")
    assert ipaddress.IPv4Network(("192.0.2.1", 24), strict=False) == net
    assert ipaddress.IPv4Network((ip, 24), strict=False) == net
    assert ipaddress.IPv4Network((3221225985, 24), strict=False) == net
    assert ipaddress.IPv4Network(("192.0.2.1", "255.255.255.0"), strict=False) == net
    assert ipaddress.IPv4Network((ip, "255.255.255.0"), strict=False) == net
    assert ipaddress.IPv4Network((3221225985, "255.255.255.0"), strict=False) == net

    # /24
    ip = ipaddress.IPv4Address("192.0.2.0")
    net = ipaddress.IPv4Network("192.0.2.0/24")
    assert ipaddress.IPv4Network(("192.0.2.0", "255.255.255.0")) == net
    assert ipaddress.IPv4Network((ip, "255.255.255.0")) == net
    assert ipaddress.IPv4Network((3221225984, "255.255.255.0")) == net
    assert ipaddress.IPv4Network(("192.0.2.0", 24)) == net
    assert ipaddress.IPv4Network((ip, 24)) == net
    assert ipaddress.IPv4Network((3221225984, 24)) == net

    assert ipaddress.IPv4Interface(("192.0.2.1", 24)) == ipaddress.IPv4Interface(
        "192.0.2.1/24"
    )
    assert ipaddress.IPv4Interface((3221225985, 24)) == ipaddress.IPv4Interface(
        "192.0.2.1/24"
    )


# issue #16531: constructing IPv6Network from an (address, mask) tuple
def test_ipv6_tuple():
    # /128
    ip = ipaddress.IPv6Address("2001:db8::")
    net = ipaddress.IPv6Network("2001:db8::/128")
    assert ipaddress.IPv6Network(("2001:db8::", "128")) == net
    assert ipaddress.IPv6Network((42540766411282592856903984951653826560, 128)) == net

    assert ipaddress.IPv6Network((ip, "128")) == net
    ip = ipaddress.IPv6Address("2001:db8::")
    net = ipaddress.IPv6Network("2001:db8::/96")
    assert ipaddress.IPv6Network(("2001:db8::", "96")) == net
    assert ipaddress.IPv6Network((42540766411282592856903984951653826560, 96)) == net
    assert ipaddress.IPv6Network((ip, "96")) == net

    ip_scoped = ipaddress.IPv6Address("2001:db8::%scope")

    # strict=True and host bits set
    ip = ipaddress.IPv6Address("2001:db8::1")
    pytest.raises(ValueError, ipaddress.IPv6Network, ("2001:db8::1", 96))
    pytest.raises(
        ValueError, ipaddress.IPv6Network, (42540766411282592856903984951653826561, 96)
    )
    pytest.raises(ValueError, ipaddress.IPv6Network, (ip, 96))
    # strict=False and host bits set
    net = ipaddress.IPv6Network("2001:db8::/96")
    assert ipaddress.IPv6Network(("2001:db8::1", 96), strict=False) == net
    assert (
        ipaddress.IPv6Network(
            (42540766411282592856903984951653826561, 96), strict=False
        )
        == net
    )
    assert ipaddress.IPv6Network((ip, 96), strict=False) == net

    # /96
    assert ipaddress.IPv6Interface(("2001:db8::1", "96")) == ipaddress.IPv6Interface(
        "2001:db8::1/96"
    )
    assert ipaddress.IPv6Interface(
        (42540766411282592856903984951653826561, "96")
    ) == ipaddress.IPv6Interface("2001:db8::1/96")

    ip_scoped = ipaddress.IPv6Address("2001:db8::1%scope")
    pytest.raises(ValueError, ipaddress.IPv6Network, ("2001:db8::1%scope", 96))
    pytest.raises(ValueError, ipaddress.IPv6Network, (ip_scoped, 96))
    # strict=False and host bits set


# issue57
def test_address_int_math():
    assert ipaddress.IPv4Address("1.1.1.1") + 255 == ipaddress.IPv4Address("1.1.2.0")
    assert ipaddress.IPv4Address("1.1.1.1") - 256 == ipaddress.IPv4Address("1.1.0.1")
    assert ipaddress.IPv6Address("::1") + (2**16 - 2) == ipaddress.IPv6Address(
        "::ffff"
    )
    assert ipaddress.IPv6Address("::ffff") - (2**16 - 2) == ipaddress.IPv6Address(
        "::1"
    )
    assert ipaddress.IPv6Address("::1%scope") + (2**16 - 2) != ipaddress.IPv6Address(
        "::ffff%scope"
    )
    assert ipaddress.IPv6Address("::ffff%scope") - (
        2**16 - 2
    ) != ipaddress.IPv6Address("::1%scope")


def test_invalid_int_to_bytes():
    pytest.raises(ValueError, ipaddress.v4_int_to_packed, -1)
    pytest.raises(ValueError, ipaddress.v4_int_to_packed, 2**ipaddress.IPV4LENGTH)
    pytest.raises(ValueError, ipaddress.v6_int_to_packed, -1)
    pytest.raises(ValueError, ipaddress.v6_int_to_packed, 2**ipaddress.IPV6LENGTH)


def test_internals(ipv4_network):
    ip1 = ipaddress.IPv4Address("10.10.10.10")
    ip2 = ipaddress.IPv4Address("10.10.10.11")
    ip3 = ipaddress.IPv4Address("10.10.10.12")
    assert list(ipaddress._find_address_range([ip1])) == [(ip1, ip1)]
    assert list(ipaddress._find_address_range([ip1, ip3])) == [(ip1, ip1), (ip3, ip3)]
    assert list(ipaddress._find_address_range([ip1, ip2, ip3])) == [(ip1, ip3)]
    assert 128 == ipaddress._count_righthand_zero_bits(0, 128)
    assert "IPv4Network('1.2.3.0/24')" == repr(ipv4_network)


def test_get_network(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert int(ipv4_network.network_address) == 16909056
    assert str(ipv4_network.network_address) == "1.2.3.0"

    assert int(ipv6_network.network_address) == 42540616829182469433403647294022090752
    assert str(ipv6_network.network_address) == "2001:658:22a:cafe::"
    assert str(ipv6_network.hostmask) == "::ffff:ffff:ffff:ffff"
    assert (
        int(ipv6_scoped_network.network_address)
        == 42540616829182469433403647294022090752
    )
    assert str(ipv6_scoped_network.network_address) == "2001:658:22a:cafe::%scope"
    assert str(ipv6_scoped_network.hostmask) == "::ffff:ffff:ffff:ffff"


def test_ip_from_int(
    ipv4_interface,
    ipv6_interface,
    ipv6_scoped_interface,
    ipv4_address,
    ipv6_address,
    ipv6_scoped_address,
):
    assert ipv4_interface._ip == ipaddress.IPv4Interface(16909060)._ip

    ipv4 = ipaddress.ip_network("1.2.3.4")
    ipv6 = ipaddress.ip_network("2001:658:22a:cafe:200:0:0:1")
    ipv6_scoped = ipaddress.ip_network("2001:658:22a:cafe:200:0:0:1%scope")
    assert ipv4 == ipaddress.ip_network(int(ipv4.network_address))
    assert ipv6 == ipaddress.ip_network(int(ipv6.network_address))
    assert ipv6_scoped != ipaddress.ip_network(int(ipv6_scoped.network_address))

    v6_int = 42540616829182469433547762482097946625
    assert ipv6_interface._ip == ipaddress.IPv6Interface(v6_int)._ip
    assert ipv6_scoped_interface._ip == ipaddress.IPv6Interface(v6_int)._ip
    assert ipaddress.ip_network(ipv4_address._ip).version == 4
    assert ipaddress.ip_network(ipv6_address._ip).version == 6
    assert ipaddress.ip_network(ipv6_scoped_address._ip).version == 6


def test_ip_from_packed(ipv4_interface, ipv6_interface):
    address = ipaddress.ip_address
    assert ipv4_interface._ip == ipaddress.ip_interface(b"\x01\x02\x03\x04")._ip
    assert address("255.254.253.252") == address(b"\xff\xfe\xfd\xfc")
    assert (
        ipv6_interface.ip
        == ipaddress.ip_interface(
            b"\x20\x01\x06\x58\x02\x2a\xca\xfe\x02\x00\x00\x00\x00\x00\x00\x01"
        ).ip
    )
    assert address("ffff:2:3:4:ffff::") == address(
        b"\xff\xff\x00\x02\x00\x03\x00\x04" + b"\xff\xff" + b"\x00" * 6
    )
    assert address("::") == address(b"\x00" * 16)


def test_get_ip(ipv4_interface, ipv6_interface, ipv6_scoped_interface):
    assert int(ipv4_interface.ip) == 16909060
    assert str(ipv4_interface.ip) == "1.2.3.4"

    assert int(ipv6_interface.ip) == 42540616829182469433547762482097946625
    assert str(ipv6_interface.ip) == "2001:658:22a:cafe:200::1"
    assert int(ipv6_scoped_interface.ip) == 42540616829182469433547762482097946625
    assert str(ipv6_scoped_interface.ip) == "2001:658:22a:cafe:200::1"


def test_get_scope_id(
    ipv6_address,
    ipv6_scoped_address,
    ipv6_interface,
    ipv6_scoped_interface,
    ipv6_network,
    ipv6_scoped_network,
):
    assert ipv6_address.scope_id is None
    assert str(ipv6_scoped_address.scope_id) == "scope"
    assert ipv6_interface.scope_id is None
    assert str(ipv6_scoped_interface.scope_id) == "scope"
    assert ipv6_network.network_address.scope_id is None
    assert str(ipv6_scoped_network.network_address.scope_id) == "scope"


def test_get_netmask(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert int(ipv4_network.netmask) == 4294967040
    assert str(ipv4_network.netmask) == "255.255.255.0"
    assert int(ipv6_network.netmask) == 340282366920938463444927863358058659840
    assert ipv6_network.prefixlen == 64
    assert int(ipv6_scoped_network.netmask) == 340282366920938463444927863358058659840
    assert ipv6_scoped_network.prefixlen == 64


def test_nero_netmask():
    ipv4_zero_netmask = ipaddress.IPv4Interface("1.2.3.4/0")
    assert int(ipv4_zero_netmask.network.netmask) == 0
    assert ipv4_zero_netmask._prefix_from_prefix_string("0") == 0

    ipv6_zero_netmask = ipaddress.IPv6Interface("::1/0")
    assert int(ipv6_zero_netmask.network.netmask) == 0
    assert ipv6_zero_netmask._prefix_from_prefix_string("0") == 0

    ipv6_scoped_zero_netmask = ipaddress.IPv6Interface("::1%scope/0")
    assert int(ipv6_scoped_zero_netmask.network.netmask) == 0
    assert ipv6_scoped_zero_netmask._prefix_from_prefix_string("0") == 0


def test_ipv4_net():
    net = ipaddress.IPv4Network("127.0.0.0/0.0.0.255")
    assert net.prefixlen == 24


def test_get_broadcast(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert int(ipv4_network.broadcast_address) == 16909311
    assert str(ipv4_network.broadcast_address) == "1.2.3.255"

    assert int(ipv6_network.broadcast_address) == 42540616829182469451850391367731642367
    assert (
        str(ipv6_network.broadcast_address) == "2001:658:22a:cafe:ffff:ffff:ffff:ffff"
    )

    assert (
        int(ipv6_scoped_network.broadcast_address)
        == 42540616829182469451850391367731642367
    )
    assert (
        str(ipv6_scoped_network.broadcast_address)
        == "2001:658:22a:cafe:ffff:ffff:ffff:ffff"
    )


def test_get_prefixlen(ipv4_interface, ipv6_interface, ipv6_scoped_interface):
    assert ipv4_interface.network.prefixlen == 24
    assert ipv6_interface.network.prefixlen == 64
    assert ipv6_scoped_interface.network.prefixlen == 64


def test_get_supernet(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert ipv4_network.supernet().prefixlen == 23
    assert str(ipv4_network.supernet().network_address) == "1.2.2.0"
    assert ipaddress.IPv4Interface(
        "0.0.0.0/0"
    ).network.supernet() == ipaddress.IPv4Network("0.0.0.0/0")

    assert ipv6_network.supernet().prefixlen == 63
    assert str(ipv6_network.supernet().network_address) == "2001:658:22a:cafe::"
    assert ipaddress.IPv6Interface("::0/0").network.supernet() == ipaddress.IPv6Network(
        "::0/0"
    )
    assert ipv6_scoped_network.supernet().prefixlen == 63
    assert str(ipv6_scoped_network.supernet().network_address) == "2001:658:22a:cafe::"


def test_get_supernet_3(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert ipv4_network.supernet(3).prefixlen == 21
    assert str(ipv4_network.supernet(3).network_address) == "1.2.0.0"

    assert ipv6_network.supernet(3).prefixlen == 61
    assert str(ipv6_network.supernet(3).network_address) == "2001:658:22a:caf8::"
    assert ipv6_scoped_network.supernet(3).prefixlen == 61
    assert str(ipv6_scoped_network.supernet(3).network_address) == "2001:658:22a:caf8::"


def test_get_supernet_4(ipv4_network, ipv6_network, ipv6_scoped_network):
    pytest.raises(ValueError, ipv4_network.supernet, prefixlen_diff=2, new_prefix=1)
    pytest.raises(ValueError, ipv4_network.supernet, new_prefix=25)
    assert ipv4_network.supernet(prefixlen_diff=2) == ipv4_network.supernet(
        new_prefix=22
    )

    pytest.raises(ValueError, ipv6_network.supernet, prefixlen_diff=2, new_prefix=1)
    pytest.raises(ValueError, ipv6_network.supernet, new_prefix=65)
    assert ipv6_network.supernet(prefixlen_diff=2) == ipv6_network.supernet(
        new_prefix=62
    )
    pytest.raises(
        ValueError,
        ipv6_scoped_network.supernet,
        prefixlen_diff=2,
        new_prefix=1,
    )
    pytest.raises(ValueError, ipv6_scoped_network.supernet, new_prefix=65)
    assert ipv6_scoped_network.supernet(
        prefixlen_diff=2
    ) == ipv6_scoped_network.supernet(new_prefix=62)


def test_hosts(ipv4_network):
    hosts = list(ipv4_network.hosts())
    assert 254 == len(hosts)
    assert ipaddress.IPv4Address("1.2.3.1") == hosts[0]
    assert ipaddress.IPv4Address("1.2.3.254") == hosts[-1]

    ipv6_network = ipaddress.IPv6Network("2001:658:22a:cafe::/120")
    hosts = list(ipv6_network.hosts())
    assert 255 == len(hosts)
    assert ipaddress.IPv6Address("2001:658:22a:cafe::1") == hosts[0]
    assert ipaddress.IPv6Address("2001:658:22a:cafe::ff") == hosts[-1]

    ipv6_scoped_network = ipaddress.IPv6Network("2001:658:22a:cafe::%scope/120")
    hosts = list(ipv6_scoped_network.hosts())
    assert 255 == len(hosts)
    assert ipaddress.IPv6Address("2001:658:22a:cafe::1") == hosts[0]
    assert ipaddress.IPv6Address("2001:658:22a:cafe::ff") == hosts[-1]

    # special case where only 1 bit is left for address
    addrs = [ipaddress.IPv4Address("2.0.0.0"), ipaddress.IPv4Address("2.0.0.1")]
    str_args = "2.0.0.0/31"
    tpl_args = ("2.0.0.0", 31)
    assert addrs == list(ipaddress.ip_network(str_args).hosts())
    assert addrs == list(ipaddress.ip_network(tpl_args).hosts())
    assert list(ipaddress.ip_network(str_args).hosts()) == list(
        ipaddress.ip_network(tpl_args).hosts()
    )

    # special case where the network is a /32
    addrs = [ipaddress.IPv4Address("1.2.3.4")]
    str_args = "1.2.3.4/32"
    tpl_args = ("1.2.3.4", 32)
    assert addrs == list(ipaddress.ip_network(str_args).hosts())
    assert addrs == list(ipaddress.ip_network(tpl_args).hosts())
    assert list(ipaddress.ip_network(str_args).hosts()) == list(
        ipaddress.ip_network(tpl_args).hosts()
    )

    addrs = [
        ipaddress.IPv6Address("2001:658:22a:cafe::"),
        ipaddress.IPv6Address("2001:658:22a:cafe::1"),
    ]
    str_args = "2001:658:22a:cafe::/127"
    tpl_args = ("2001:658:22a:cafe::", 127)
    assert addrs == list(ipaddress.ip_network(str_args).hosts())
    assert addrs == list(ipaddress.ip_network(tpl_args).hosts())
    assert list(ipaddress.ip_network(str_args).hosts()) == list(
        ipaddress.ip_network(tpl_args).hosts()
    )

    addrs = [
        ipaddress.IPv6Address("2001:658:22a:cafe::1"),
    ]
    str_args = "2001:658:22a:cafe::1/128"
    tpl_args = ("2001:658:22a:cafe::1", 128)
    assert addrs == list(ipaddress.ip_network(str_args).hosts())
    assert addrs == list(ipaddress.ip_network(tpl_args).hosts())
    assert list(ipaddress.ip_network(str_args).hosts()) == list(
        ipaddress.ip_network(tpl_args).hosts()
    )


def test_fancy_subnetting(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert sorted(ipv4_network.subnets(prefixlen_diff=3)) == sorted(
        ipv4_network.subnets(new_prefix=27)
    )
    pytest.raises(ValueError, list, ipv4_network.subnets(new_prefix=23))
    pytest.raises(
        ValueError, list, ipv4_network.subnets(prefixlen_diff=3, new_prefix=27)
    )
    assert sorted(ipv6_network.subnets(prefixlen_diff=4)) == sorted(
        ipv6_network.subnets(new_prefix=68)
    )
    pytest.raises(ValueError, list, ipv6_network.subnets(new_prefix=63))
    pytest.raises(
        ValueError, list, ipv6_network.subnets(prefixlen_diff=4, new_prefix=68)
    )
    assert sorted(ipv6_scoped_network.subnets(prefixlen_diff=4)) == sorted(
        ipv6_scoped_network.subnets(new_prefix=68)
    )
    pytest.raises(ValueError, list, ipv6_scoped_network.subnets(new_prefix=63))
    pytest.raises(
        ValueError,
        list,
        ipv6_scoped_network.subnets(prefixlen_diff=4, new_prefix=68),
    )


def test_get_subnets(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert list(ipv4_network.subnets())[0].prefixlen == 25
    assert str(list(ipv4_network.subnets())[0].network_address) == "1.2.3.0"
    assert str(list(ipv4_network.subnets())[1].network_address) == "1.2.3.128"

    assert list(ipv6_network.subnets())[0].prefixlen == 65
    assert list(ipv6_scoped_network.subnets())[0].prefixlen == 65


def test_get_subnet_for_single_32():
    ip = ipaddress.IPv4Network("1.2.3.4/32")
    subnets1 = [str(x) for x in ip.subnets()]
    subnets2 = [str(x) for x in ip.subnets(2)]
    assert subnets1 == ["1.2.3.4/32"]
    assert subnets1 == subnets2


def test_get_subnet_for_Single_128():
    ip = ipaddress.IPv6Network("::1/128")
    subnets1 = [str(x) for x in ip.subnets()]
    subnets2 = [str(x) for x in ip.subnets(2)]
    assert subnets1 == ["::1/128"]
    assert subnets1 == subnets2

    ip_scoped = ipaddress.IPv6Network("::1%scope/128")
    subnets1 = [str(x) for x in ip_scoped.subnets()]
    subnets2 = [str(x) for x in ip_scoped.subnets(2)]
    assert subnets1 == ["::1%scope/128"]
    assert subnets1 == subnets2


def test_subnet_2(ipv4_network, ipv6_network):
    ips = [str(x) for x in ipv4_network.subnets(2)]
    assert ips == ["1.2.3.0/26", "1.2.3.64/26", "1.2.3.128/26", "1.2.3.192/26"]

    ipsv6 = [str(x) for x in ipv6_network.subnets(2)]
    assert ipsv6 == [
        "2001:658:22a:cafe::/66",
        "2001:658:22a:cafe:4000::/66",
        "2001:658:22a:cafe:8000::/66",
        "2001:658:22a:cafe:c000::/66",
    ]


def test_get_subnets_3(ipv4_network):
    subnets = [str(x) for x in ipv4_network.subnets(8)]
    assert subnets[:3] == ["1.2.3.0/32", "1.2.3.1/32", "1.2.3.2/32"]
    assert subnets[-3:] == ["1.2.3.253/32", "1.2.3.254/32", "1.2.3.255/32"]
    assert len(subnets) == 256

    ipv6_network = ipaddress.IPv6Network("2001:658:22a:cafe::/120")
    subnets = [str(x) for x in ipv6_network.subnets(8)]
    assert subnets[:3] == [
        "2001:658:22a:cafe::/128",
        "2001:658:22a:cafe::1/128",
        "2001:658:22a:cafe::2/128",
    ]
    assert subnets[-3:] == [
        "2001:658:22a:cafe::fd/128",
        "2001:658:22a:cafe::fe/128",
        "2001:658:22a:cafe::ff/128",
    ]
    assert len(subnets) == 256


def test_subnet_fails_for_large_cidr_diff(
    ipv4_interface,
    ipv4_network,
    ipv6_interface,
    ipv6_network,
    ipv6_scoped_interface,
    ipv6_scoped_network,
):
    pytest.raises(ValueError, list, ipv4_interface.network.subnets(9))
    pytest.raises(ValueError, list, ipv4_network.subnets(9))
    pytest.raises(ValueError, list, ipv6_interface.network.subnets(65))
    pytest.raises(ValueError, list, ipv6_network.subnets(65))
    pytest.raises(ValueError, list, ipv6_scoped_interface.network.subnets(65))
    pytest.raises(ValueError, list, ipv6_scoped_network.subnets(65))


def test_supernet_fails_for_large_cidr_diff(
    ipv4_interface, ipv6_interface, ipv6_scoped_interface
):
    pytest.raises(ValueError, ipv4_interface.network.supernet, 25)
    pytest.raises(ValueError, ipv6_interface.network.supernet, 65)
    pytest.raises(ValueError, ipv6_scoped_interface.network.supernet, 65)


def test_subnet_fails_for_negative_cidr_diff(
    ipv4_interface,
    ipv4_network,
    ipv6_interface,
    ipv6_network,
    ipv6_scoped_interface,
    ipv6_scoped_network,
):
    pytest.raises(ValueError, list, ipv4_interface.network.subnets(-1))
    pytest.raises(ValueError, list, ipv4_network.subnets(-1))
    pytest.raises(ValueError, list, ipv6_interface.network.subnets(-1))
    pytest.raises(ValueError, list, ipv6_network.subnets(-1))
    pytest.raises(ValueError, list, ipv6_scoped_interface.network.subnets(-1))
    pytest.raises(ValueError, list, ipv6_scoped_network.subnets(-1))


def test_get_num_addresses(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert ipv4_network.num_addresses == 256
    assert list(ipv4_network.subnets())[0].num_addresses == 128
    assert ipv4_network.supernet().num_addresses == 512

    assert ipv6_network.num_addresses == 18446744073709551616
    assert list(ipv6_network.subnets())[0].num_addresses == 9223372036854775808
    assert ipv6_network.supernet().num_addresses == 36893488147419103232
    assert ipv6_scoped_network.num_addresses == 18446744073709551616
    assert list(ipv6_scoped_network.subnets())[0].num_addresses == 9223372036854775808
    assert ipv6_scoped_network.supernet().num_addresses == 36893488147419103232


def test_contains(ipv4_network):
    assert ipaddress.IPv4Interface("1.2.3.128/25") in ipv4_network
    assert ipaddress.IPv4Interface("1.2.4.1/24") not in ipv4_network
    # We can test addresses and string as well.
    addr1 = ipaddress.IPv4Address("1.2.3.37")
    assert addr1 in ipv4_network
    # issue 61, bad network comparison on like-ip'd network objects
    # with identical broadcast addresses.
    assert (
        ipaddress.IPv4Network("1.1.0.0/16").__contains__(
            ipaddress.IPv4Network("1.0.0.0/15")
        )
        is False
    )


def test_nth(ipv4_network, ipv6_network, ipv6_scoped_network):
    assert str(ipv4_network[5]) == "1.2.3.5"
    pytest.raises(IndexError, ipv4_network.__getitem__, 256)

    assert str(ipv6_network[5]) == "2001:658:22a:cafe::5"
    pytest.raises(IndexError, ipv6_network.__getitem__, 1 << 64)
    assert str(ipv6_scoped_network[5]) == "2001:658:22a:cafe::5"
    pytest.raises(IndexError, ipv6_scoped_network.__getitem__, 1 << 64)


def test_get_item():
    # http://code.google.com/p/ipaddr-py/issues/detail?id=15
    addr = ipaddress.IPv4Network("172.31.255.128/255.255.255.240")
    assert 28 == addr.prefixlen
    addr_list = list(addr)
    assert "172.31.255.128" == str(addr_list[0])
    assert "172.31.255.128" == str(addr[0])
    assert "172.31.255.143" == str(addr_list[-1])
    assert "172.31.255.143" == str(addr[-1])
    assert addr_list[-1] == addr[-1]


def test_equal(ipv4_interface, ipv6_interface, ipv6_scoped_interface):
    assert ipv4_interface == ipaddress.IPv4Interface("1.2.3.4/24")
    assert not ipv4_interface == ipaddress.IPv4Interface("1.2.3.4/23")
    assert not ipv4_interface == ipaddress.IPv6Interface("::1.2.3.4/24")
    assert not ipv4_interface == ipaddress.IPv6Interface("::1.2.3.4%scope/24")
    assert not ipv4_interface == ""
    assert not ipv4_interface == []
    assert not ipv4_interface == 2

    assert ipv6_interface == ipaddress.IPv6Interface("2001:658:22a:cafe:200::1/64")
    assert not ipv6_interface == ipaddress.IPv6Interface("2001:658:22a:cafe:200::1/63")
    assert not ipv6_interface == ipaddress.IPv4Interface("1.2.3.4/23")
    assert not ipv6_interface == ""
    assert not ipv6_interface == []
    assert not ipv6_interface == 2

    assert ipv6_scoped_interface == ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1%scope/64"
    )
    assert not ipv6_scoped_interface == ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1%scope/63"
    )
    assert not ipv6_scoped_interface == ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1/64"
    )
    assert not ipv6_scoped_interface == ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1/63"
    )
    assert not ipv6_scoped_interface == ipaddress.IPv4Interface("1.2.3.4/23")
    assert not ipv6_scoped_interface == ""
    assert not ipv6_scoped_interface == []
    assert not ipv6_scoped_interface == 2


def test_not_equal(
    ipv4_interface,
    ipv6_interface,
    ipv6_scoped_interface,
    ipv4_address,
    ipv6_address,
    ipv6_scoped_address,
):
    assert not ipv4_interface != ipaddress.IPv4Interface("1.2.3.4/24")
    assert ipv4_interface != ipaddress.IPv4Interface("1.2.3.4/23")
    assert ipv4_interface != ipaddress.IPv6Interface("::1.2.3.4/24")
    assert ipv4_interface != ipaddress.IPv6Interface("::1.2.3.4%scope/24")
    assert ipv4_interface != ""
    assert ipv4_interface != []
    assert ipv4_interface != 2

    assert ipv4_address != ipaddress.IPv4Address("1.2.3.5")
    assert ipv4_address != ""
    assert ipv4_address != []
    assert ipv4_address != 2

    assert not ipv6_interface != ipaddress.IPv6Interface("2001:658:22a:cafe:200::1/64")
    assert ipv6_interface != ipaddress.IPv6Interface("2001:658:22a:cafe:200::1/63")
    assert ipv6_interface != ipaddress.IPv4Interface("1.2.3.4/23")
    assert ipv6_interface != ""
    assert ipv6_interface != []
    assert ipv6_interface != 2

    assert ipv6_address != ipaddress.IPv4Address("1.2.3.4")
    assert ipv6_address != ""
    assert ipv6_address != []
    assert ipv6_address != 2

    assert not ipv6_scoped_interface != ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1%scope/64"
    )
    assert ipv6_scoped_interface != ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1%scope/63"
    )
    assert ipv6_scoped_interface != ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1/64"
    )
    assert ipv6_scoped_interface != ipaddress.IPv6Interface(
        "2001:658:22a:cafe:200::1/63"
    )
    assert ipv6_scoped_interface != ipaddress.IPv4Interface("1.2.3.4/23")
    assert ipv6_scoped_interface != ""
    assert ipv6_scoped_interface != []
    assert ipv6_scoped_interface != 2

    assert ipv6_scoped_address != ipaddress.IPv4Address("1.2.3.4")
    assert ipv6_scoped_address != ""
    assert ipv6_scoped_address != []
    assert ipv6_scoped_address != 2


def test_slash_32_constructor():
    assert str(ipaddress.IPv4Interface("1.2.3.4/255.255.255.255")) == "1.2.3.4/32"


def test_slash_128_constructor():
    assert str(ipaddress.IPv6Interface("::1/128")) == "::1/128"
    assert str(ipaddress.IPv6Interface("::1%scope/128")) == "::1%scope/128"


def test_slash_0_constructor():
    assert str(ipaddress.IPv4Interface("1.2.3.4/0.0.0.0")) == "1.2.3.4/0"


def test_collapsing():
    # test only IP addresses including some duplicates
    ip1 = ipaddress.IPv4Address("1.1.1.0")
    ip2 = ipaddress.IPv4Address("1.1.1.1")
    ip3 = ipaddress.IPv4Address("1.1.1.2")
    ip4 = ipaddress.IPv4Address("1.1.1.3")
    ip5 = ipaddress.IPv4Address("1.1.1.4")
    ip6 = ipaddress.IPv4Address("1.1.1.0")
    # check that addresses are subsumed properly.
    collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3, ip4, ip5, ip6])
    assert list(collapsed) == [
        ipaddress.IPv4Network("1.1.1.0/30"),
        ipaddress.IPv4Network("1.1.1.4/32"),
    ]

    # test a mix of IP addresses and networks including some duplicates
    ip1 = ipaddress.IPv4Address("1.1.1.0")
    ip2 = ipaddress.IPv4Address("1.1.1.1")
    ip3 = ipaddress.IPv4Address("1.1.1.2")
    ip4 = ipaddress.IPv4Address("1.1.1.3")
    # ip5 = ipaddress.IPv4Interface('1.1.1.4/30')
    # ip6 = ipaddress.IPv4Interface('1.1.1.4/30')
    # check that addresses are subsumed properly.
    collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3, ip4])
    assert list(collapsed) == [ipaddress.IPv4Network("1.1.1.0/30")]

    # test only IP networks
    ip1 = ipaddress.IPv4Network("1.1.0.0/24")
    ip2 = ipaddress.IPv4Network("1.1.1.0/24")
    ip3 = ipaddress.IPv4Network("1.1.2.0/24")
    ip4 = ipaddress.IPv4Network("1.1.3.0/24")
    ip5 = ipaddress.IPv4Network("1.1.4.0/24")
    # stored in no particular order b/c we want CollapseAddr to call
    # [].sort
    ip6 = ipaddress.IPv4Network("1.1.0.0/22")
    # check that addresses are subsumed properly.
    collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3, ip4, ip5, ip6])
    assert list(collapsed) == [
        ipaddress.IPv4Network("1.1.0.0/22"),
        ipaddress.IPv4Network("1.1.4.0/24"),
    ]

    # test that two addresses are supernet'ed properly
    collapsed = ipaddress.collapse_addresses([ip1, ip2])
    assert list(collapsed) == [ipaddress.IPv4Network("1.1.0.0/23")]

    # test same IP networks
    ip_same1 = ip_same2 = ipaddress.IPv4Network("1.1.1.1/32")
    assert list(ipaddress.collapse_addresses([ip_same1, ip_same2])) == [ip_same1]

    # test same IP addresses
    ip_same1 = ip_same2 = ipaddress.IPv4Address("1.1.1.1")
    assert list(ipaddress.collapse_addresses([ip_same1, ip_same2])) == [
        ipaddress.ip_network("1.1.1.1/32")
    ]

    ip1 = ipaddress.IPv6Network("2001::/100")
    ip2 = ipaddress.IPv6Network("2001::/120")
    ip3 = ipaddress.IPv6Network("2001::/96")
    # test that ipv6 addresses are subsumed properly.
    collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3])
    assert list(collapsed) == [ip3]

    ip1 = ipaddress.IPv6Network("2001::%scope/100")
    ip2 = ipaddress.IPv6Network("2001::%scope/120")
    ip3 = ipaddress.IPv6Network("2001::%scope/96")
    # test that ipv6 addresses are subsumed properly.
    collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3])
    assert list(collapsed) == [ip3]

    # the toejam test
    addr_tuples = [
        (ipaddress.ip_address("1.1.1.1"), ipaddress.ip_address("::1")),
        (ipaddress.IPv4Network("1.1.0.0/24"), ipaddress.IPv6Network("2001::/120")),
        (ipaddress.IPv4Network("1.1.0.0/32"), ipaddress.IPv6Network("2001::/128")),
    ]
    for ip1, ip2 in addr_tuples:
        pytest.raises(TypeError, ipaddress.collapse_addresses, [ip1, ip2])

    addr_tuples = [
        (ipaddress.ip_address("1.1.1.1"), ipaddress.ip_address("::1%scope")),
        (
            ipaddress.IPv4Network("1.1.0.0/24"),
            ipaddress.IPv6Network("2001::%scope/120"),
        ),
        (
            ipaddress.IPv4Network("1.1.0.0/32"),
            ipaddress.IPv6Network("2001::%scope/128"),
        ),
    ]
    for ip1, ip2 in addr_tuples:
        pytest.raises(TypeError, ipaddress.collapse_addresses, [ip1, ip2])


def test_summarizing():
    # ip = ipaddress.ip_address
    # ipnet = ipaddress.ip_network
    summarize = ipaddress.summarize_address_range
    ip1 = ipaddress.ip_address("1.1.1.0")
    ip2 = ipaddress.ip_address("1.1.1.255")

    # summarize works only for IPv4 & IPv6
    class IPv7Address(ipaddress.IPv6Address):
        @property
        def version(self):
            return 7

    ip_invalid1 = IPv7Address("::1")
    ip_invalid2 = IPv7Address("::1")
    pytest.raises(ValueError, list, summarize(ip_invalid1, ip_invalid2))
    # test that a summary over ip4 & ip6 fails
    pytest.raises(TypeError, list, summarize(ip1, ipaddress.IPv6Address("::1")))
    pytest.raises(TypeError, list, summarize(ip1, ipaddress.IPv6Address("::1%scope")))
    # test a /24 is summarized properly
    assert list(summarize(ip1, ip2))[0] == ipaddress.ip_network("1.1.1.0/24")
    # test an IPv4 range that isn't on a network byte boundary
    ip2 = ipaddress.ip_address("1.1.1.8")
    assert list(summarize(ip1, ip2)) == [
        ipaddress.ip_network("1.1.1.0/29"),
        ipaddress.ip_network("1.1.1.8"),
    ]

    # all!
    ip1 = ipaddress.IPv4Address(0)
    ip2 = ipaddress.IPv4Address(ipaddress.IPv4Address._ALL_ONES)
    assert [ipaddress.IPv4Network("0.0.0.0/0")] == list(summarize(ip1, ip2))

    ip1 = ipaddress.ip_address("1::")
    ip2 = ipaddress.ip_address("1:ffff:ffff:ffff:ffff:ffff:ffff:ffff")
    # test an IPv6 is summarized properly
    assert list(summarize(ip1, ip2))[0] == ipaddress.ip_network("1::/16")
    # test an IPv6 range that isn't on a network byte boundary
    ip2 = ipaddress.ip_address("2::")
    assert list(summarize(ip1, ip2)) == [
        ipaddress.ip_network("1::/16"),
        ipaddress.ip_network("2::/128"),
    ]

    ip1 = ipaddress.ip_address("1::%scope")
    ip2 = ipaddress.ip_address("1:ffff:ffff:ffff:ffff:ffff:ffff:ffff%scope")
    # test an IPv6 is summarized properly
    assert list(summarize(ip1, ip2))[0] == ipaddress.ip_network("1::/16")
    # test an IPv6 range that isn't on a network byte boundary
    ip2 = ipaddress.ip_address("2::%scope")
    assert list(summarize(ip1, ip2)) == [
        ipaddress.ip_network("1::/16"),
        ipaddress.ip_network("2::/128"),
    ]

    # test exception raised when first is greater than last
    pytest.raises(
        ValueError,
        list,
        summarize(ipaddress.ip_address("1.1.1.0"), ipaddress.ip_address("1.1.0.0")),
    )
    # test exception raised when first and last aren't IP addresses
    pytest.raises(
        TypeError,
        list,
        summarize(ipaddress.ip_network("1.1.1.0"), ipaddress.ip_network("1.1.0.0")),
    )
    pytest.raises(
        TypeError,
        list,
        summarize(ipaddress.ip_network("1.1.1.0"), ipaddress.ip_network("1.1.0.0")),
    )
    # test exception raised when first and last are not same version
    pytest.raises(
        TypeError,
        list,
        summarize(ipaddress.ip_address("::"), ipaddress.ip_network("1.1.0.0")),
    )


def test_address_comparison():
    assert ipaddress.ip_address("1.1.1.1") <= ipaddress.ip_address("1.1.1.1")
    assert ipaddress.ip_address("1.1.1.1") <= ipaddress.ip_address("1.1.1.2")
    assert ipaddress.ip_address("::1") <= ipaddress.ip_address("::1")
    assert ipaddress.ip_address("::1") <= ipaddress.ip_address("::2")
    assert ipaddress.ip_address("::1%scope") <= ipaddress.ip_address("::1%scope")
    assert ipaddress.ip_address("::1%scope") <= ipaddress.ip_address("::2%scope")


def test_interface_comparison():
    assert ipaddress.ip_interface("1.1.1.1/24") == ipaddress.ip_interface("1.1.1.1/24")
    assert ipaddress.ip_interface("1.1.1.1/16") < ipaddress.ip_interface("1.1.1.1/24")
    assert ipaddress.ip_interface("1.1.1.1/24") < ipaddress.ip_interface("1.1.1.2/24")
    assert ipaddress.ip_interface("1.1.1.2/16") < ipaddress.ip_interface("1.1.1.1/24")
    assert ipaddress.ip_interface("1.1.1.1/24") > ipaddress.ip_interface("1.1.1.1/16")
    assert ipaddress.ip_interface("1.1.1.2/24") > ipaddress.ip_interface("1.1.1.1/24")
    assert ipaddress.ip_interface("1.1.1.1/24") > ipaddress.ip_interface("1.1.1.2/16")

    assert ipaddress.ip_interface("::1/64") == ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::1/64") < ipaddress.ip_interface("::1/80")
    assert ipaddress.ip_interface("::1/64") < ipaddress.ip_interface("::2/64")
    assert ipaddress.ip_interface("::2/48") < ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::1/80") > ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::2/64") > ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::1/64") > ipaddress.ip_interface("::2/48")

    assert ipaddress.ip_interface("::1%scope/64") == ipaddress.ip_interface(
        "::1%scope/64"
    )
    assert ipaddress.ip_interface("::1%scope/64") < ipaddress.ip_interface(
        "::1%scope/80"
    )
    assert ipaddress.ip_interface("::1%scope/64") < ipaddress.ip_interface(
        "::2%scope/64"
    )
    assert ipaddress.ip_interface("::2%scope/48") < ipaddress.ip_interface(
        "::1%scope/64"
    )
    assert ipaddress.ip_interface("::1%scope/80") > ipaddress.ip_interface(
        "::1%scope/64"
    )
    assert ipaddress.ip_interface("::2%scope/64") > ipaddress.ip_interface(
        "::1%scope/64"
    )
    assert ipaddress.ip_interface("::1%scope/64") > ipaddress.ip_interface(
        "::2%scope/48"
    )

    assert ipaddress.ip_interface("::1%scope/64") != ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::1%scope/64") < ipaddress.ip_interface("::1/80")
    assert ipaddress.ip_interface("::1%scope/64") < ipaddress.ip_interface("::2/64")
    assert ipaddress.ip_interface("::2%scope/48") < ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::1%scope/80") > ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::2%scope/64") > ipaddress.ip_interface("::1/64")
    assert ipaddress.ip_interface("::1%scope/64") > ipaddress.ip_interface("::2/48")

    assert ipaddress.ip_interface("::1/64") != ipaddress.ip_interface("::1%scope/64")
    assert ipaddress.ip_interface("::1/64") < ipaddress.ip_interface("::1%scope/80")
    assert ipaddress.ip_interface("::1/64") < ipaddress.ip_interface("::2%scope/64")
    assert ipaddress.ip_interface("::2/48") < ipaddress.ip_interface("::1%scope/64")
    assert ipaddress.ip_interface("::1/80") > ipaddress.ip_interface("::1%scope/64")
    assert ipaddress.ip_interface("::2/64") > ipaddress.ip_interface("::1%scope/64")
    assert ipaddress.ip_interface("::1/64") > ipaddress.ip_interface("::2%scope/48")


def test_network_comparison(ipv4_network, ipv6_network):
    # ip1 and ip2 have the same network address
    ip1 = ipaddress.IPv4Network("1.1.1.0/24")
    ip2 = ipaddress.IPv4Network("1.1.1.0/32")
    ip3 = ipaddress.IPv4Network("1.1.2.0/24")

    assert ip1 < ip3
    assert ip3 > ip2

    assert ip1.compare_networks(ip1) == 0

    # if addresses are the same, sort by netmask
    assert ip1.compare_networks(ip2) == -1
    assert ip2.compare_networks(ip1) == 1

    assert ip1.compare_networks(ip3) == -1
    assert ip3.compare_networks(ip1) == 1
    assert ip1._get_networks_key() < ip3._get_networks_key()

    ip1 = ipaddress.IPv6Network("2001:2000::/96")
    ip2 = ipaddress.IPv6Network("2001:2001::/96")
    ip3 = ipaddress.IPv6Network("2001:ffff:2000::/96")

    assert ip1 < ip3
    assert ip3 > ip2
    assert ip1.compare_networks(ip3) == -1
    assert ip1._get_networks_key() < ip3._get_networks_key()

    # Test comparing different protocols.
    # Should always raise a TypeError.
    pytest.raises(TypeError, ipv4_network.compare_networks, ipv6_network)
    ipv6 = ipaddress.IPv6Interface("::/0")
    ipv4 = ipaddress.IPv4Interface("0.0.0.0/0")
    pytest.raises(TypeError, ipv4.__lt__, ipv6)
    pytest.raises(TypeError, ipv4.__gt__, ipv6)
    pytest.raises(TypeError, ipv6.__lt__, ipv4)
    pytest.raises(TypeError, ipv6.__gt__, ipv4)

    # Regression test for issue 19.
    ip1 = ipaddress.ip_network("10.1.2.128/25")
    assert not ip1 < ip1
    assert not ip1 > ip1
    ip2 = ipaddress.ip_network("10.1.3.0/24")
    assert ip1 < ip2
    assert not ip2 < ip1
    assert not ip1 > ip2
    assert ip2 > ip1
    ip3 = ipaddress.ip_network("10.1.3.0/25")
    assert ip2 < ip3
    assert not ip3 < ip2
    assert not ip2 > ip3
    assert ip3 > ip2

    # Regression test for issue 28.
    ip1 = ipaddress.ip_network("10.10.10.0/31")
    ip2 = ipaddress.ip_network("10.10.10.0")
    ip3 = ipaddress.ip_network("10.10.10.2/31")
    ip4 = ipaddress.ip_network("10.10.10.2")
    sorted = [ip1, ip2, ip3, ip4]
    unsorted = [ip2, ip4, ip1, ip3]
    unsorted.sort()
    assert sorted == unsorted
    unsorted = [ip4, ip1, ip3, ip2]
    unsorted.sort()
    assert sorted == unsorted
    assert ip1.__lt__(ipaddress.ip_address("10.10.10.0")) is NotImplemented
    assert ip2.__lt__(ipaddress.ip_address("10.10.10.0")) is NotImplemented

    # <=, >=
    assert ipaddress.ip_network("1.1.1.1") <= ipaddress.ip_network("1.1.1.1")
    assert ipaddress.ip_network("1.1.1.1") <= ipaddress.ip_network("1.1.1.2")
    assert not ipaddress.ip_network("1.1.1.2") <= ipaddress.ip_network("1.1.1.1")

    assert ipaddress.ip_network("::1") <= ipaddress.ip_network("::1")
    assert ipaddress.ip_network("::1") <= ipaddress.ip_network("::2")
    assert not ipaddress.ip_network("::2") <= ipaddress.ip_network("::1")


def test_strict_networks():
    pytest.raises(ValueError, ipaddress.ip_network, "192.168.1.1/24")
    pytest.raises(ValueError, ipaddress.ip_network, "::1/120")
    pytest.raises(ValueError, ipaddress.ip_network, "::1%scope/120")


def test_overlaps(ipv4_network):
    other = ipaddress.IPv4Network("1.2.3.0/30")
    other2 = ipaddress.IPv4Network("1.2.2.0/24")
    other3 = ipaddress.IPv4Network("1.2.2.64/26")
    assert ipv4_network.overlaps(other) is True
    assert ipv4_network.overlaps(other2) is False
    assert other2.overlaps(other3) is True


def test_embedded_ipv4():
    ipv4_string = "192.168.0.1"
    ipv4 = ipaddress.IPv4Interface(ipv4_string)
    v4compat_ipv6 = ipaddress.IPv6Interface("::%s" % ipv4_string)
    assert int(v4compat_ipv6.ip) == int(ipv4.ip)
    v4mapped_ipv6 = ipaddress.IPv6Interface("::ffff:%s" % ipv4_string)
    assert v4mapped_ipv6.ip != ipv4.ip
    pytest.raises(
        ipaddress.AddressValueError, ipaddress.IPv6Interface, "2001:1.1.1.1:1.1.1.1"
    )


# Issue 67: IPv6 with embedded IPv4 address not recognized.
def test_ipv6_address_too_large():
    # RFC4291 2.5.5.2
    assert ipaddress.ip_address("::FFFF:192.0.2.1") == ipaddress.ip_address(
        "::FFFF:c000:201"
    )
    # RFC4291 2.2 (part 3) x::d.d.d.d
    assert ipaddress.ip_address("FFFF::192.0.2.1") == ipaddress.ip_address(
        "FFFF::c000:201"
    )

    assert ipaddress.ip_address("::FFFF:192.0.2.1%scope") == ipaddress.ip_address(
        "::FFFF:c000:201%scope"
    )
    assert ipaddress.ip_address("FFFF::192.0.2.1%scope") == ipaddress.ip_address(
        "FFFF::c000:201%scope"
    )
    assert ipaddress.ip_address("::FFFF:192.0.2.1%scope") != ipaddress.ip_address(
        "::FFFF:c000:201"
    )
    assert ipaddress.ip_address("FFFF::192.0.2.1%scope") != ipaddress.ip_address(
        "FFFF::c000:201"
    )
    assert ipaddress.ip_address("::FFFF:192.0.2.1") != ipaddress.ip_address(
        "::FFFF:c000:201%scope"
    )
    assert ipaddress.ip_address("FFFF::192.0.2.1") != ipaddress.ip_address(
        "FFFF::c000:201%scope"
    )


def test_ip_version(ipv4_address, ipv6_address, ipv6_scoped_address):
    assert ipv4_address.version == 4
    assert ipv6_address.version == 6
    assert ipv6_scoped_address.version == 6


def test_max_prefix_length(ipv4_interface, ipv6_interface, ipv6_scoped_interface):
    assert ipv4_interface.max_prefixlen == 32
    assert ipv6_interface.max_prefixlen == 128
    assert ipv6_scoped_interface.max_prefixlen == 128


def test_packed(ipv4_address, ipv6_address, ipv6_scoped_address):
    assert ipv4_address.packed == b"\x01\x02\x03\x04"
    assert ipaddress.IPv4Interface("255.254.253.252").packed == b"\xff\xfe\xfd\xfc"
    assert (
        ipv6_address.packed
        == b"\x20\x01\x06\x58\x02\x2a\xca\xfe\x02\x00\x00\x00\x00\x00\x00\x01"
    )
    assert (
        ipaddress.IPv6Interface("ffff:2:3:4:ffff::").packed
        == b"\xff\xff\x00\x02\x00\x03\x00\x04\xff\xff" + b"\x00" * 6
    )
    assert (
        ipaddress.IPv6Interface("::1:0:0:0:0").packed
        == b"\x00" * 6 + b"\x00\x01" + b"\x00" * 8
    )
    assert (
        ipv6_scoped_address.packed
        == b"\x20\x01\x06\x58\x02\x2a\xca\xfe\x02\x00\x00\x00\x00\x00\x00\x01"
    )
    assert (
        ipaddress.IPv6Interface("ffff:2:3:4:ffff::%scope").packed
        == b"\xff\xff\x00\x02\x00\x03\x00\x04\xff\xff" + b"\x00" * 6
    )
    assert (
        ipaddress.IPv6Interface("::1:0:0:0:0%scope").packed
        == b"\x00" * 6 + b"\x00\x01" + b"\x00" * 8
    )


def test_ip_type():
    ipv4net = ipaddress.ip_network("1.2.3.4")
    ipv4addr = ipaddress.ip_address("1.2.3.4")
    ipv6net = ipaddress.ip_network("::1.2.3.4")
    ipv6addr = ipaddress.ip_address("::1.2.3.4")
    assert ipaddress.IPv4Network == type(ipv4net)
    assert ipaddress.IPv4Address == type(ipv4addr)
    assert ipaddress.IPv6Network == type(ipv6net)
    assert ipaddress.IPv6Address == type(ipv6addr)


def test_reserved_ipv4():
    # test networks
    assert ipaddress.ip_interface("224.1.1.1/31").is_multicast is True
    assert ipaddress.ip_network("240.0.0.0").is_multicast is False
    assert ipaddress.ip_network("240.0.0.0").is_reserved is True

    assert ipaddress.ip_interface("192.168.1.1/17").is_private is True
    assert ipaddress.ip_network("192.169.0.0").is_private is False
    assert ipaddress.ip_network("10.255.255.255").is_private is True
    assert ipaddress.ip_network("11.0.0.0").is_private is False
    assert ipaddress.ip_network("11.0.0.0").is_reserved is False
    assert ipaddress.ip_network("172.31.255.255").is_private is True
    assert ipaddress.ip_network("172.32.0.0").is_private is False
    assert ipaddress.ip_network("169.254.1.0/24").is_link_local is True

    assert ipaddress.ip_interface("169.254.100.200/24").is_link_local is True
    assert ipaddress.ip_interface("169.255.100.200/24").is_link_local is False

    assert ipaddress.ip_network("127.100.200.254/32").is_loopback is True
    assert ipaddress.ip_network("127.42.0.0/16").is_loopback is True
    assert ipaddress.ip_network("128.0.0.0").is_loopback is False
    assert ipaddress.ip_network("100.64.0.0/10").is_private is False
    assert ipaddress.ip_network("100.64.0.0/10").is_global is False

    assert ipaddress.ip_network("192.0.2.128/25").is_private is True
    assert ipaddress.ip_network("192.0.3.0/24").is_global is True

    # test addresses
    assert ipaddress.ip_address("0.0.0.0").is_unspecified is True
    assert ipaddress.ip_address("224.1.1.1").is_multicast is True
    assert ipaddress.ip_address("240.0.0.0").is_multicast is False
    assert ipaddress.ip_address("240.0.0.1").is_reserved is True
    assert ipaddress.ip_address("239.255.255.255").is_reserved is False

    assert ipaddress.ip_address("192.168.1.1").is_private is True
    assert ipaddress.ip_address("192.169.0.0").is_private is False
    assert ipaddress.ip_address("10.255.255.255").is_private is True
    assert ipaddress.ip_address("11.0.0.0").is_private is False
    assert ipaddress.ip_address("172.31.255.255").is_private is True
    assert ipaddress.ip_address("172.32.0.0").is_private is False

    assert ipaddress.ip_address("169.254.100.200").is_link_local is True
    assert ipaddress.ip_address("169.255.100.200").is_link_local is False

    assert ipaddress.ip_address("192.0.7.1").is_global is True
    assert ipaddress.ip_address("203.0.113.1").is_global is False

    assert ipaddress.ip_address("127.100.200.254").is_loopback is True
    assert ipaddress.ip_address("127.42.0.0").is_loopback is True
    assert ipaddress.ip_address("128.0.0.0").is_loopback is False
    assert ipaddress.ip_network("0.0.0.0").is_unspecified is True


def test_reserved_ipv6():

    assert ipaddress.ip_network("ffff::").is_multicast is True
    assert ipaddress.ip_network(2**128 - 1).is_multicast is True
    assert ipaddress.ip_network("ff00::").is_multicast is True
    assert ipaddress.ip_network("fdff::").is_multicast is False

    assert ipaddress.ip_network("fecf::").is_site_local is True
    assert ipaddress.ip_network("feff:ffff:ffff:ffff::").is_site_local is True
    assert ipaddress.ip_network("fbf:ffff::").is_site_local is False
    assert ipaddress.ip_network("ff00::").is_site_local is False

    assert ipaddress.ip_network("fc00::").is_private is True
    assert ipaddress.ip_network("fc00:ffff:ffff:ffff::").is_private is True
    assert ipaddress.ip_network("fbff:ffff::").is_private is False
    assert ipaddress.ip_network("fe00::").is_private is False

    assert ipaddress.ip_network("fea0::").is_link_local is True
    assert ipaddress.ip_network("febf:ffff::").is_link_local is True
    assert ipaddress.ip_network("fe7f:ffff::").is_link_local is False
    assert ipaddress.ip_network("fec0::").is_link_local is False

    assert ipaddress.ip_interface("0:0::0:01").is_loopback is True
    assert ipaddress.ip_interface("::1/127").is_loopback is False
    assert ipaddress.ip_network("::").is_loopback is False
    assert ipaddress.ip_network("::2").is_loopback is False

    assert ipaddress.ip_network("0::0").is_unspecified is True
    assert ipaddress.ip_network("::1").is_unspecified is False
    assert ipaddress.ip_network("::/127").is_unspecified is False

    assert ipaddress.ip_network("2001::1/128").is_private is True
    assert ipaddress.ip_network("200::1/128").is_global is True
    # test addresses
    assert ipaddress.ip_address("ffff::").is_multicast is True
    assert ipaddress.ip_address(2**128 - 1).is_multicast is True
    assert ipaddress.ip_address("ff00::").is_multicast is True
    assert ipaddress.ip_address("fdff::").is_multicast is False

    assert ipaddress.ip_address("fecf::").is_site_local is True
    assert ipaddress.ip_address("feff:ffff:ffff:ffff::").is_site_local is True
    assert ipaddress.ip_address("fbf:ffff::").is_site_local is False
    assert ipaddress.ip_address("ff00::").is_site_local is False

    assert ipaddress.ip_address("fc00::").is_private is True
    assert ipaddress.ip_address("fc00:ffff:ffff:ffff::").is_private is True
    assert ipaddress.ip_address("fbff:ffff::").is_private is False
    assert ipaddress.ip_address("fe00::").is_private is False

    assert ipaddress.ip_address("fea0::").is_link_local is True
    assert ipaddress.ip_address("febf:ffff::").is_link_local is True
    assert ipaddress.ip_address("fe7f:ffff::").is_link_local is False
    assert ipaddress.ip_address("fec0::").is_link_local is False

    assert ipaddress.ip_address("0:0::0:01").is_loopback is True
    assert ipaddress.ip_address("::1").is_loopback is True
    assert ipaddress.ip_address("::2").is_loopback is False

    assert ipaddress.ip_address("0::0").is_unspecified is True
    assert ipaddress.ip_address("::1").is_unspecified is False

    # some generic IETF reserved addresses
    assert ipaddress.ip_address("100::").is_reserved is True
    assert ipaddress.ip_network("4000::1/128").is_reserved is True


def test_ipv4_mapped():
    assert ipaddress.ip_address(
        "::ffff:192.168.1.1"
    ).ipv4_mapped == ipaddress.ip_address("192.168.1.1")
    assert ipaddress.ip_address("::c0a8:101").ipv4_mapped is None
    assert ipaddress.ip_address("::ffff:c0a8:101").ipv4_mapped == ipaddress.ip_address(
        "192.168.1.1"
    )


def test_addr_exclude():
    addr1 = ipaddress.ip_network("10.1.1.0/24")
    addr2 = ipaddress.ip_network("10.1.1.0/26")
    addr3 = ipaddress.ip_network("10.2.1.0/24")
    addr4 = ipaddress.ip_address("10.1.1.0")
    addr5 = ipaddress.ip_network("2001:db8::0/32")
    addr6 = ipaddress.ip_network("10.1.1.5/32")
    assert sorted(list(addr1.address_exclude(addr2))) == [
        ipaddress.ip_network("10.1.1.64/26"),
        ipaddress.ip_network("10.1.1.128/25"),
    ]
    pytest.raises(ValueError, list, addr1.address_exclude(addr3))
    pytest.raises(TypeError, list, addr1.address_exclude(addr4))
    pytest.raises(TypeError, list, addr1.address_exclude(addr5))
    assert list(addr1.address_exclude(addr1)) == []
    assert sorted(list(addr1.address_exclude(addr6))) == [
        ipaddress.ip_network("10.1.1.0/30"),
        ipaddress.ip_network("10.1.1.4/32"),
        ipaddress.ip_network("10.1.1.6/31"),
        ipaddress.ip_network("10.1.1.8/29"),
        ipaddress.ip_network("10.1.1.16/28"),
        ipaddress.ip_network("10.1.1.32/27"),
        ipaddress.ip_network("10.1.1.64/26"),
        ipaddress.ip_network("10.1.1.128/25"),
    ]


def test_hash(ipv4_address, ipv6_address):
    assert hash(ipaddress.ip_interface("10.1.1.0/24")) == hash(
        ipaddress.ip_interface("10.1.1.0/24")
    )
    assert hash(ipaddress.ip_network("10.1.1.0/24")) == hash(
        ipaddress.ip_network("10.1.1.0/24")
    )
    assert hash(ipaddress.ip_address("10.1.1.0")) == hash(
        ipaddress.ip_address("10.1.1.0")
    )
    # i70
    assert hash(ipaddress.ip_address("1.2.3.4")) == hash(
        ipaddress.ip_address(int(ipaddress.ip_address("1.2.3.4")._ip))
    )
    ip1 = ipaddress.ip_address("10.1.1.0")
    ip2 = ipaddress.ip_address("1::")
    dummy = {}
    dummy[ipv4_address] = None
    dummy[ipv6_address] = None
    dummy[ip1] = None
    dummy[ip2] = None
    assert ipv4_address in dummy
    assert ip2 in dummy


def test_ip_bases(ipv4_network, ipv6_network):
    net = ipv4_network
    assert "1.2.3.0/24" == net.compressed
    net = ipv6_network
    pytest.raises(ValueError, net._string_from_ip_int, 2**128 + 1)


def test_ipv6_network_helpers(ipv6_network):
    net = ipv6_network
    assert "2001:658:22a:cafe::/64" == net.with_prefixlen
    assert "2001:658:22a:cafe::/ffff:ffff:ffff:ffff::" == net.with_netmask
    assert "2001:658:22a:cafe::/::ffff:ffff:ffff:ffff" == net.with_hostmask
    assert "2001:658:22a:cafe::/64" == str(net)


def test_ipv4_network_helpers(ipv4_network):
    net = ipv4_network
    assert "1.2.3.0/24" == net.with_prefixlen
    assert "1.2.3.0/255.255.255.0" == net.with_netmask
    assert "1.2.3.0/0.0.0.255" == net.with_hostmask
    assert "1.2.3.0/24" == str(net)


def test_copy_constructor():
    addr1 = ipaddress.ip_network("10.1.1.0/24")
    addr2 = ipaddress.ip_network(addr1)
    addr3 = ipaddress.ip_interface("2001:658:22a:cafe:200::1/64")
    addr4 = ipaddress.ip_interface(addr3)
    addr5 = ipaddress.IPv4Address("1.1.1.1")
    addr6 = ipaddress.IPv6Address("2001:658:22a:cafe:200::1")

    assert addr1 == addr2
    assert addr3 == addr4
    assert addr5 == ipaddress.IPv4Address(addr5)
    assert addr6 == ipaddress.IPv6Address(addr6)


def test_compress_ipv6_address():
    test_addresses = {
        "1:2:3:4:5:6:7:8": "1:2:3:4:5:6:7:8/128",
        "2001:0:0:4:0:0:0:8": "2001:0:0:4::8/128",
        "2001:0:0:4:5:6:7:8": "2001::4:5:6:7:8/128",
        "2001:0:3:4:5:6:7:8": "2001:0:3:4:5:6:7:8/128",
        "0:0:3:0:0:0:0:ffff": "0:0:3::ffff/128",
        "0:0:0:4:0:0:0:ffff": "::4:0:0:0:ffff/128",
        "0:0:0:0:5:0:0:ffff": "::5:0:0:ffff/128",
        "1:0:0:4:0:0:7:8": "1::4:0:0:7:8/128",
        "0:0:0:0:0:0:0:0": "::/128",
        "0:0:0:0:0:0:0:0/0": "::/0",
        "0:0:0:0:0:0:0:1": "::1/128",
        "2001:0658:022a:cafe:0000:0000:0000:0000/66": "2001:658:22a:cafe::/66",
        "::1.2.3.4": "::102:304/128",
        "1:2:3:4:5:ffff:1.2.3.4": "1:2:3:4:5:ffff:102:304/128",
        "::7:6:5:4:3:2:1": "0:7:6:5:4:3:2:1/128",
        "::7:6:5:4:3:2:0": "0:7:6:5:4:3:2:0/128",
        "7:6:5:4:3:2:1::": "7:6:5:4:3:2:1:0/128",
        "0:6:5:4:3:2:1::": "0:6:5:4:3:2:1:0/128",
    }
    for uncompressed, compressed in list(test_addresses.items()):
        assert compressed == str(ipaddress.IPv6Interface(uncompressed))


def test_explode_short_hand_ip_str():
    addr1 = ipaddress.IPv6Interface("2001::1")
    addr2 = ipaddress.IPv6Address("2001:0:5ef5:79fd:0:59d:a0e5:ba1")
    addr3 = ipaddress.IPv6Network("2001::/96")
    addr4 = ipaddress.IPv4Address("192.168.178.1")
    assert "2001:0000:0000:0000:0000:0000:0000:0001/128" == addr1.exploded
    assert (
        "0000:0000:0000:0000:0000:0000:0000:0001/128"
        == ipaddress.IPv6Interface("::1/128").exploded
    )
    # issue 77
    assert "2001:0000:5ef5:79fd:0000:059d:a0e5:0ba1" == addr2.exploded
    assert "2001:0000:0000:0000:0000:0000:0000:0000/96" == addr3.exploded
    assert "192.168.178.1" == addr4.exploded


def test_reverse_pointer():
    addr1 = ipaddress.IPv4Address("127.0.0.1")
    addr2 = ipaddress.IPv6Address("2001:db8::1")
    assert "1.0.0.127.in-addr.arpa" == addr1.reverse_pointer
    assert (
        "1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa"
        == addr2.reverse_pointer
    )


def test_int_representation(ipv4_address, ipv6_address):
    assert 16909060 == int(ipv4_address)
    assert 42540616829182469433547762482097946625 == int(ipv6_address)


def test_force_version():
    assert ipaddress.ip_network(1).version == 4
    assert ipaddress.IPv6Network(1).version == 6


def test_with_star(ipv4_interface, ipv6_interface):
    assert ipv4_interface.with_prefixlen == "1.2.3.4/24"
    assert ipv4_interface.with_netmask == "1.2.3.4/255.255.255.0"
    assert ipv4_interface.with_hostmask == "1.2.3.4/0.0.0.255"

    assert ipv6_interface.with_prefixlen == "2001:658:22a:cafe:200::1/64"
    assert (
        ipv6_interface.with_netmask == "2001:658:22a:cafe:200::1/ffff:ffff:ffff:ffff::"
    )
    # this probably doesn't make much sense, but it's included for
    # compatibility with ipv4
    assert (
        ipv6_interface.with_hostmask == "2001:658:22a:cafe:200::1/::ffff:ffff:ffff:ffff"
    )


def test_network_element_caching(ipv4_network, ipv6_network, ipv6_interface):
    # V4 - make sure we're empty
    assert "broadcast_address" not in ipv4_network._cache
    assert "hostmask" not in ipv4_network._cache

    # V4 - populate and test
    assert ipv4_network.broadcast_address == ipaddress.IPv4Address("1.2.3.255")
    assert ipv4_network.hostmask == ipaddress.IPv4Address("0.0.0.255")

    # V4 - check we're cached
    assert "broadcast_address" in ipv4_network._cache
    assert "hostmask" in ipv4_network._cache

    # V6 - make sure we're empty
    assert "broadcast_address" not in ipv6_network._cache
    assert "hostmask" not in ipv6_network._cache

    # V6 - populate and test
    assert ipv6_network.network_address == ipaddress.IPv6Address("2001:658:22a:cafe::")
    assert ipv6_interface.network.network_address == ipaddress.IPv6Address(
        "2001:658:22a:cafe::"
    )

    assert ipv6_network.broadcast_address == ipaddress.IPv6Address(
        "2001:658:22a:cafe:ffff:ffff:ffff:ffff"
    )
    assert ipv6_network.hostmask == ipaddress.IPv6Address("::ffff:ffff:ffff:ffff")

    assert ipv6_interface.network.broadcast_address == ipaddress.IPv6Address(
        "2001:658:22a:cafe:ffff:ffff:ffff:ffff"
    )
    assert ipv6_interface.network.hostmask == ipaddress.IPv6Address(
        "::ffff:ffff:ffff:ffff"
    )

    # V6 - check we're cached
    assert "broadcast_address" in ipv6_network._cache
    assert "hostmask" in ipv6_network._cache
    assert "broadcast_address" in ipv6_interface.network._cache
    assert "hostmask" in ipv6_interface.network._cache


def test_teredo():
    # stolen from wikipedia
    server = ipaddress.IPv4Address("65.54.227.120")
    client = ipaddress.IPv4Address("192.0.2.45")
    teredo_addr = "2001:0000:4136:e378:8000:63bf:3fff:fdd2"
    assert (server, client) == ipaddress.ip_address(teredo_addr).teredo
    bad_addr = "2000::4136:e378:8000:63bf:3fff:fdd2"
    assert ipaddress.ip_address(bad_addr).teredo is None
    bad_addr = "2001:0001:4136:e378:8000:63bf:3fff:fdd2"
    assert ipaddress.ip_address(bad_addr).teredo is None

    # i77
    teredo_addr = ipaddress.IPv6Address("2001:0:5ef5:79fd:0:59d:a0e5:ba1")
    assert (
        ipaddress.IPv4Address("94.245.121.253"),
        ipaddress.IPv4Address("95.26.244.94"),
    ) == teredo_addr.teredo


def test_sixtofour():
    sixtofouraddr = ipaddress.ip_address("2002:ac1d:2d64::1")
    bad_addr = ipaddress.ip_address("2000:ac1d:2d64::1")
    assert ipaddress.IPv4Address("172.29.45.100") == sixtofouraddr.sixtofour
    assert bad_addr.sixtofour is None


# issue41004 Hash collisions in IPv4Interface and IPv6Interface
def test_v4_hash_is_not_constant():
    ipv4_address1 = ipaddress.IPv4Interface("1.2.3.4")
    ipv4_address2 = ipaddress.IPv4Interface("2.3.4.5")
    assert ipv4_address1.__hash__() != ipv4_address2.__hash__()


# issue41004 Hash collisions in IPv4Interface and IPv6Interface
def test_v6_hash_is_not_constant():
    ipv6_address1 = ipaddress.IPv6Interface("2001:658:22a:cafe:200:0:0:1")
    ipv6_address2 = ipaddress.IPv6Interface("2001:658:22a:cafe:200:0:0:2")
    assert ipv6_address1.__hash__() != ipv6_address2.__hash__()
